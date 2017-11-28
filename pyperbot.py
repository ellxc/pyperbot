# coding=utf-8
import asyncio
import copy
import importlib
import inspect
import logging
import os
import pickle
import re
import traceback
from collections import namedtuple, ChainMap

import datetime
from pyparsing import ParseException

from Message import Message
from client import IrcClient
from events import EventManager
from piping import PipeManager, piperror
from pyperparser import total, inners, pipeline as pipline
from util import MutableNameSpace, missingarg, envnotdef, CommandNotDefined, toomany, aString, shitHandler

Plugin = namedtuple('plugin',
                    'instance, triggers, commands, regexes, crons, events, outputfilters, onloads, unloads, syncs, envs')

class Pyperbot:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.clients = {}
        self.em = EventManager(loop=loop)
        self.PipeManager = PipeManager()
        self.plugins = {}
        self.aliases = {}
        self.em.register_handler("PRIVMSG", lambda message: asyncio.ensure_future(self.handle_message(message)))
        self.env = {}
        self.userspaces = {}
        self.admins = {}
        try:
            with open("aliases", 'r') as alias_file:
                for line in alias_file.readlines():
                    name, _, pipe = line.strip().partition("=")
                    self.aliases[name] = pipe
        except FileNotFoundError:
            pass



            # if shell:
            #     import repl
            #     self.clients['repl'] = repl.repl(self.loop, self.em)
            #     self.clients['repl'].start()

    def run(self):
        # with shelve.open('userspaces', writeback=True) as self.userspaces:
        #     for serv in self.clients:
        #         if serv not in self.userspaces:
        #             self.userspaces[serv] = {}
        #     with shelve.open('env', writeback=True) as self.env:
        try:
            self.userspaces = pickle.load(open("userspaces.pickle", "rb"))
        except FileNotFoundError:
            pass
        for serv in self.clients:
            if serv not in self.userspaces:
                self.userspaces[serv] = {}
        try:
            self.env = pickle.load(open("env.pickle", "rb"))
        except FileNotFoundError:
            pass

        self.loop.call_later(10, self.cronshim)
        self.loop.run_forever()

        with open("aliases", 'w+') as alias_file:
            for name, pipe in self.aliases.items():
                alias_file.write((name + "=" + pipe + "\n"))
        pickle.dump(self.userspaces, open("userspaces.pickle", "wb"))
        pickle.dump(self.env, open("env.pickle", "wb"))

    def cronshim(self, *funcs):
        if funcs:
            for func in funcs:
                func()
        nxt, fnc = None, []
        now = datetime.datetime.utcnow()
        for crn, [*fnk] in self.crons.items():
            if nxt is None or crn.next(now=now, default_utc=True) < nxt.next(now=now, default_utc=True):
                nxt, fnc = crn, [*fnk]
            elif crn.next(now=now, default_utc=True) == nxt.next(now=now, default_utc=True):
                for fnkk in fnk:
                    fnc.append(fnkk)

        if nxt is None:
            delay = 60
        else:
            delay = nxt.next(now=now, default_utc=True)
        self.loop.call_later(delay, lambda: self.cronshim(*fnc))



    def connect_to(self, servername, host, port, nick="pyperbot", channels=[], admins=None, password=None,
                   username=None, ssl=False):
        temp = IrcClient(host, port, loop=self.loop, ssl=ssl, username=username, password=password,
                         nick=nick, servername=servername)
        temp.em.parent = self.em
        temp.em.name = servername
        if channels:
            temp.em.register_handler("001",
                                     lambda **kwargs: temp.send(Message(command="JOIN", params=" ".join(channels))))

        self.loop.run_until_complete(temp.connect())
        self.clients[servername] = temp

    async def is_authed(self, msg):
        if not self.admins or msg.server not in self.admins or msg.nick not in self.admins[msg.server]:
            return False

        f = asyncio.Future(loop=self.loop)
        state = []

        def auth_handler(message):
            state.append(message)
            if "Last seen  : now" in message.text:
                f.set_result(True)
            elif not f.done() and ("is not registered." in message.text or "End of Info" in message.text):
                f.set_result(False)

        self.clients[msg.server].em.register_handler('NOTICE', auth_handler)
        self.send(Message(server=msg.server, command="PRIVMSG", params="NickServ", text="INFO %s" % msg.nick))
        res = await f
        self.clients[msg.server].em.deregister_handler('NOTICE', auth_handler)

        # is identified
        return res

    def send(self, message):
        if message.server in self.clients:
            self.clients[message.server].send(message)
            if 0 and message.command == "PRIVMSG":  # TODO: buffers
                temp = message.copy()
                temp.nick = self.clients[message.server].nick
                # self.message_buffer[message.server][message.params].appendleft(temp)
        else:
            raise Exception("no such server: " + message.server)

    def load_plugin_file(self, plugin, config={}):
        handlers = []
        if "." in plugin:
            module = "".join(plugin.split(".")[:-1])
            plugin_name = plugin.split(".")[-1]
            temp = importlib.machinery.SourceFileLoader(module, os.path.dirname(
                os.path.abspath(__file__)) + "/plugins/" + module + ".py").load_module()
            found = False
            for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
                if name == plugin_name:
                    handlers.append(Class)
                    found = True
                    self.load_plugin(plugin, Class, config=config)
        else:
            temp = importlib.machinery.SourceFileLoader(plugin, os.path.dirname(
                os.path.abspath(__file__)) + "/plugins/" + plugin + ".py").load_module()
            found = False
            for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
                handlers.append(Class)
                self.load_plugin(name, Class, config=config)
                found = True
            if not found:
                raise Exception("no such plugin to load or file did not contain a plugin")
        return handlers

    def load_plugin(self, name, plugin, config={}):
        print("loading plugin: " + plugin.__class__.__name__)
        crons = {}
        events = {}
        triggers = {}
        regexes = {}
        commands = {}
        outputfilters = []
        onloads = []
        unloads = []
        syncs = []
        envs = {}
        instance = plugin(self, config=config)
        for _, func in inspect.getmembers(instance):
            if hasattr(func, "_crons"):
                for cr in func._crons:
                    if cr not in crons:
                        crons[cr] = []
                    crons[cr].append(func)
            if hasattr(func, "_events"):
                for ev in func._events:
                    if ev not in events:
                        events[ev] = []
                    events[ev].append(func)
            if hasattr(func, "_triggers"):
                for trig in func._triggers:
                    if trig not in triggers:
                        triggers[trig] = []
                    triggers[trig].append(func)
            if hasattr(func, "_regexes"):
                for reg in func._regexes:
                    if reg not in regexes:
                        regexes[reg] = []
                    regexes[reg].append(func)
            if hasattr(func, "_commands"):
                for word in func._commands:
                    commands[word] = func
            if hasattr(func, "_outputfilter"):
                outputfilters.append((func._outputfilter, func))
            if hasattr(func, "_onload"):
                onloads.append(func)
            if hasattr(func, "_unload"):
                unloads.append(func)
            if hasattr(func, "_sync"):
                syncs.append(func)
            if hasattr(func, "_envs"):
                for env in func._envs:
                    envs[env] = func
        self.plugins[name] = Plugin(instance=instance, crons=crons, events=events, triggers=triggers, regexes=regexes,
                                    commands=commands, outputfilters=outputfilters, onloads=onloads, unloads=unloads,
                                    syncs=syncs, envs=envs)
        for x in onloads:
            self.loop.call_soon(x)

    def unload_plugin(self, name):
        x = self.plugins[name]
        del self.plugins[name]
        for y in x.unloads:
            self.loop.call_soon(y)

    @property
    def commands(self):
        return ChainMap(*[p.commands for p in self.plugins.values()])

    @property
    def regexes(self):
        return ChainMap(*[p.regexes for p in self.plugins.values()])

    @property
    def triggers(self):
        return ChainMap(*[p.triggers for p in self.plugins.values()])

    @property
    def crons(self):
        return ChainMap(*[p.crons for p in self.plugins.values()])

    @property
    def outputfilters(self):
        return list(map(lambda x: x[1], sorted([x for y in self.plugins.values() for x in y.outputfilters],
                                               key=lambda x: x[0])))

    @property
    def syncs(self):
        return [x for y in self.plugins.values() for x in y.syncs]

    @property
    def envs(self):
        return ChainMap(*[{name: func() for name, func in x.envs.items()} for x in self.plugins.values()])

    def sync(self):
        for func in self.syncs:
            func()
        with open("aliases", 'w+') as alias_file:
            for name, pipe in self.aliases.items():
                alias_file.write((name + "=" + pipe + "\n"))
        pickle.dump(self.userspaces, open("userspaces.pickle", "wb"))
        pickle.dump(self.env, open("env.pickle", "wb"))

    async def handle_message(self, msg):
        if msg.server not in self.userspaces:
            self.userspaces[msg.server] = {}
        if msg.nick not in self.userspaces[msg.server]:
            self.userspaces[msg.server][msg.nick] = MutableNameSpace(all=True)

        if msg.text.startswith("#"):
            await self.parse_msg(msg)

        for reg, funcs in self.regexes.items():
            x = re.match(reg, msg.text)
            if x:
                for func in funcs:
                    if inspect.isawaitable(func):
                        await func(msg, x)
                    else:
                        func(msg, x)

        for trigger, func in self.triggers:
            if trigger(msg):
                if inspect.isawaitable(func):
                    await func(msg)
                else:
                    func(msg)


    async def parse_msg(self, msg):
        try:
            x = total.parseString(msg.text[1:], parseAll=True)
            print(msg.text[1:], "->", x)
            await self.run_parse(x, msg, callback=self.send, outputfilter=True)
        except ParseException as e:
            self.send(msg.reply(" " * (e.col + 1) + "^"))
            self.send(msg.reply(str(e.__class__.__name__) + ": " + e.msg))
        except envnotdef as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply(str(e.ex) + " is not defined"))
        except CommandNotDefined as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply("function " + str(e.ex) + " is not defined"))
        except piperror as e:
            self.send(msg.reply(" " * 1 + e.errstr))
            for i, ex in enumerate(e.exs):
                self.send(msg.reply(
                    ((str(i + 1) + ": ") if len(e.exs) > 1 else "") + str(ex.__class__.__name__) + ": " + str(ex)))
                try:
                    raise ex
                except Exception:  # how to print to terminal
                    traceback.print_exc()
        except toomany as e:
            self.send(msg.reply("Error: Resulting call would be too long!"))
        except missingarg as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply("MissingArg: " + e.ex))
        except Exception as e:
            # self.send(msg.reply(" " * (e.col + 1) + "^"))
            self.send(msg.reply(str(e.__class__.__name__) + ": " + str(e)))
            raise

    async def run_parse(self, tree, msg, callback=None, offset=0, preargs=[], outputfilter=False):
        y, off, x = tree[0]
        if y == "pipeline":
            return await self.run_pipeline(x, msg, callback=callback, offset=offset, preargs=preargs,
                                           outputfilter=outputfilter)
        elif y == "assignment":
            (_, _, [target]), (_, _, x) = x
            res = await self.run_pipeline(x, msg, offset=offset, preargs=preargs)  # should never filter assignments

            if res is not None and len(res) == 1:
                x = res[0].data
            else:
                x = list(map(lambda m: m.data, res))

            try:
                path = target.split(".")
                path.reverse()
                temp = ChainMap(self.env, {"self": self.userspaces[msg.server][msg.nick]})
                while len(path) > 1:
                    temp = temp[path.pop()]
                temp[path.pop()] = x
                return x
            except KeyError as e:
                raise envnotdef(offset, e)

        elif y == "alias":
            (_, _, target), pipeline = x
            self.aliases[target] = pipeline

    async def run_pipeline(self, pipeline, initial: Message, callback=None, offset=0, preargs=[], outputfilter=False):
        cmds_n_args = []
        locs = []
        async for (func, args, start) in self.funcs_n_args(pipeline, initial, offset=offset, preargs=preargs):
            cmds_n_args.append((func, initial.reply(
                text=" ".join(map(lambda x: "'%s'" % x if isinstance(x, aString) else str(x), args)), data=args)))
            locs.append(start)
        if outputfilter:
            for outfilter in self.outputfilters:
                cmds_n_args.append((outfilter, initial))
        x = self.PipeManager.run_pipe(
            cmds_n_args, loop=None,
            callback=callback)
        res, x = await x
        errstr = ""
        errs = []
        for err, location in zip(x, locs):
            if isinstance(err, SyntaxError):
                errstr += " " * (location + err.offset - len(errstr)) + "^"
                errs.append(err)
            elif isinstance(err, Exception):
                errstr += " " * (location - len(errstr)) + "^"
                errs.append(err)
        if errstr:
            errstr = " " + errstr
            raise piperror(errstr, errs)
        return res

    async def do_arg(self, arg, initial, offset=0, preargs=[]):
        arg_type, loc, s = arg
        if arg_type in ["t_nakedvar", "t_bracketvar"]:
            try:
                path = s.split(".")
                path.reverse()
                x = ChainMap(self.env, {"self": self.userspaces[initial.server][initial.nick]}, self.envs)
                while path:
                    x = x[path.pop()]
                return [[x, loc]]
            except KeyError as e:
                raise envnotdef(loc + offset, e)
        elif arg_type == "backquote":
            res = await self.run_parse(total.parseString(s, parseAll=True), initial, offset=loc + offset)
            x = list(map(lambda m: m.data, res))
            return [[x, loc]]
        elif arg_type == "doublequote":
            for x in reversed(list(inners.scanString(s))):
                toks, start, end = x
                b = " ".join(
                    str(b) for b, _ in await self.do_arg(toks[0], initial, offset=offset + loc, preargs=preargs))
                s = s[:start] + str(b) + s[end:]
            return [[aString(s), loc]]
        elif arg_type == "singlequote":
            return [[aString(s), loc]]
        elif arg_type == "homedir":
            try:
                path = s.split(".")
                path.reverse()
                x = copy.deepcopy(self.userspaces[initial.server])
                while path:
                    x = x[path.pop()]
                return [[x, loc]]
            except KeyError as e:
                raise envnotdef(loc + offset, e)
        elif arg_type == "starred":
            [[a, loc]] = await self.do_arg(s, initial, offset=offset + loc)
            return [[n, loc] for n in a]
        elif arg_type == "back_index":
            index = int(s.index)
            try:
                return [[preargs[index], loc]]
            except IndexError as e:
                raise missingarg(offset, "missing arg no:%s" % index)
        elif arg_type == "back_range":

            # if not preargs:
            #     raise Exception("this pipeline takes a parameter!")
            start = None if s.start is None else int(s.start)
            stop = None if s.stop is None else int(s.stop)
            step = None if s.step is None else int(s.step)
            try:
                # got a range

                # if a > len(preargs) or b > len(preargs):
                #     raise IndexError("This pipline needs atleast %s params!" % s[1])  #TODO make this use a custom error with location
                return [[q, loc] for q in preargs[slice(start, stop, step)]]
            except IndexError as e:
                raise missingarg(loc, "missing arg no:%s" % start)
        else:
            return [[s, loc]]

    async def funcs_n_args(self, pipeline, initial, preargs=[], offset=0, count=0):
        count = count
        for _, _, [(_, start, cmd_name), *cmd_args] in pipeline:
            if count > 50:
                raise toomany()

            args = []

            argers = [self.do_arg(x, initial, offset, preargs) for x in cmd_args]
            for shit in await asyncio.gather(*argers):
                for arg, loc in shit:
                    args.append(arg)

            if cmd_name in self.commands:
                func = self.commands[cmd_name]
                yield (func, args, start + offset)
                count += 1
            elif cmd_name in self.aliases:
                first = True
                try:
                    _, _, pip = pipline.parseString(self.aliases[cmd_name], parseAll=True)[0]
                    async for func_, args_, _ in self.funcs_n_args(pip, initial, preargs=args,
                                                                          offset=offset + start, count=count + 1):
                        yield (func_, args_, start + offset)
                        count += 1
                except missingarg as e:
                    raise missingarg(e.loc, e.ex + " for alias " + cmd_name)
            else:
                raise CommandNotDefined(offset + start, cmd_name)

    @staticmethod
    def from_config(filename):
        import json, codecs
        json_config = codecs.open(filename, 'r', 'utf-8-sig')
        config = json.load(json_config)
        loop = asyncio.get_event_loop()
        bot = Pyperbot(loop=loop)

        if "apikeys" in config:
            for api, key in config["apikeys"]:
                bot.apikeys[api] = key

        for plugin, config_ in config["plugins"].items():
            bot.load_plugin_file(plugin, config=config_)

        for server in config["servers"]:
            server_name = server["IRCNet"]
            network = server["IRCHost"]
            name = server["IRCName"]
            user = server["IRCUser"]
            port = server["IRCPort"]
            nick = server["IRCNick"]
            password = server["IRCPass"] if "IRCPass" in server else None
            autojoin = server["AutoJoin"]
            admins = server["Admins"]
            usessl = server["UseSSL"]
            bot.connect_to(server_name, network, port, ssl=usessl, username=user, password=password, nick=nick,
                           channels=autojoin)
            bot.admins[server_name] = admins

        return bot

def throw(e):
    raise e

if __name__ == "__main__":
    # from repl import stdout_shim
    #
    # sys.stdout = stdout_shim(sys.stdout)

    log = logging.getLogger("pyperbot")
    log.setLevel(logging.DEBUG)

    ch = shitHandler()

    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)
    log.addHandler(ch)

    from sys import argv

    bot = Pyperbot.from_config(argv[1])
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.sync()
