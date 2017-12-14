# coding=utf-8
import asyncio
import copy
import datetime
import importlib
import inspect
import logging
import os
import pickle
import re
import traceback
from collections import namedtuple, ChainMap, defaultdict, deque
from pyparsing import ParseException

from pyperbot.Message import Message
from pyperbot.client import IrcClient
from pyperbot.events import EventManager
from pyperbot.piping import PipeManager, PipeError
from pyperbot.pyperparser import total, inners, pipeline as pipline
from pyperbot.util import MutableNameSpace, ResultingCallTooLong, aString, bString, ShitHandler

Plugin = namedtuple('plugin',
                    'instance, triggers, commands, regexes, crons, events, outputfilters, onloads, unloads, syncs, '
                    'envs')


class Pyperbot:
    def __init__(self, loop: asyncio.AbstractEventLoop, debug=False, aliasfile='aliases', envfile='env.pickle',
                 userspacefile='userspaces.pickle'):
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
        self.message_buffer = defaultdict(lambda: defaultdict(lambda: deque(maxlen=50)))
        self.debug = debug
        self.apikeys = {}
        self.aliasfile = aliasfile
        self.envfile = envfile
        self.userspacefile = userspacefile

    def run(self):
        try:
            self.userspaces = pickle.load(open(self.userspacefile, "rb"))
        except FileNotFoundError:
            pass
        for serv in self.clients:
            if serv not in self.userspaces:
                self.userspaces[serv] = {}
        try:
            self.env = pickle.load(open(self.envfile, "rb"))
        except FileNotFoundError:
            pass

        try:
            with open(self.aliasfile, 'br') as alias_file:
                for line in alias_file.readlines():
                    line = line.decode()
                    name, _, pipe = line.strip().partition("=")
                    self.aliases[name] = pipe
        except FileNotFoundError:
            pass

        self.loop.call_later(10, self.cronshim)
        self.loop.run_forever()

        with open(self.aliasfile, 'bw+') as alias_file:
            for name, pipe in self.aliases.items():
                alias_file.write((name + "=" + pipe + "\n").encode("utf-8"))
        pickle.dump(self.userspaces, open(self.userspacefile, "wb"))
        pickle.dump(self.env, open(self.envfile, "wb"))

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
                                     lambda **kwargs: temp.send(Message(command="JOIN", params=",".join(channels))))

        self.loop.run_until_complete(temp.connect())
        self.clients[servername] = temp

    async def is_authed(self, msg):

        if msg.server == "SHELL":
            return True
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
            module_ = "".join(plugin.split(".")[:-1])
            plugin_name = plugin.split(".")[-1]
            temp = importlib.machinery.SourceFileLoader(module_, os.path.dirname(
                os.path.abspath(__file__)) + "/plugins/" + module_ + ".py").load_module()
            found = False
            for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
                if name == plugin_name:
                    handlers.append(Class)
                    found = True
                    self.load_plugin(plugin_name, Class, config=config)
        else:
            temp = importlib.machinery.SourceFileLoader(plugin, os.path.dirname(
                os.path.abspath(__file__)) + "/plugins/" + plugin + ".py").load_module()
            found = False
            for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
                handlers.append(Class)
                self.load_plugin(plugin, Class, config=config)
                found = True
        if not found:
            raise Exception("no such plugin to load or file did not contain a plugin")
        return handlers

    def load_plugin(self, name, plugin, config={}):
        print("loading plugin: " + plugin.__name__ + " / " + name)
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
        for ev, ehs in events.items():
            for eh in ehs:
                self.em.register_handler(ev, eh)

    def unload_plugin(self, name):
        x = self.plugins[name]
        del self.plugins[name]
        for y in x.unloads:
            self.loop.call_soon(y)
        for ev, ehs in x.events.items():
            for eh in ehs:
                self.em.deregister_handler(ev, eh)

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

    def get_env(self, message):
        users = copy.deepcopy(self.userspaces[message.server]) if message.server in self.userspaces else {}
        _self = self.userspaces[message.server][message.nick] if message.server in self.userspaces else {}

        return ChainMap(self.env, {"self": _self, "users": users, "msg":message}, self.envs, users)

    def sync(self):
        for func in self.syncs:
            func()
        with open(self.aliasfile, 'bw+') as alias_file:
            for name, pipe in self.aliases.items():
                alias_file.write((name + "=" + pipe + "\n").encode("utf-8"))
        pickle.dump(self.userspaces, open("userspaces.pickle", "wb"))
        pickle.dump(self.env, open("env.pickle", "wb"))

    async def handle_message(self, msg):
        if msg.server not in self.userspaces:
            self.userspaces[msg.server] = {}
        if msg.nick not in self.userspaces[msg.server]:
            self.userspaces[msg.server][msg.nick] = MutableNameSpace(recurse=False)

        if msg.text.startswith("#"):
            await self.parse_msg(msg)

        for reg, funcs in self.regexes.items():
            x = re.match(reg, msg.text)
            if x:
                for func in funcs:
                    x = func(msg, x)
                    if inspect.isawaitable(x):
                        await x

        for trigger, funcs in self.triggers.items():
            for func in funcs:
                if trigger(msg):
                    x = func(msg)
                    if inspect.isawaitable(x):
                        await x

        self.message_buffer[msg.server][msg.params].append(msg)

    async def parse_msg(self, msg):
        try:
            x = total.parseString(msg.text[1:], parseAll=True)
            print(msg.text[1:], "->", x)
            await self.run_parse(x, msg, callback=self.send, outputfilter=True, recursion_limit=20)
        except ParseException as e:
            self.send(msg.reply(" " * (e.col + 1) + "^"))
            self.send(msg.reply(str(e.__class__.__name__) + ": parse error!"))
            if self.debug:
                try:
                    raise e
                except Exception:  # how to print to terminal
                    traceback.print_exc()
        except PipeError as e:
            errstr = ""
            errs = []
            for loc, err in sorted(e.exs, key=lambda x: x[0]):
                if isinstance(err, PipeError):
                    for loc2, err2 in sorted(err.exs, key=lambda x: x[0]):
                        errstr += " " * ((loc + loc2) - len(errstr)) + "^"
                        errs.append(err2)
                        if self.debug:
                            try:
                                raise err2
                            except Exception:  # how to print to terminal
                                traceback.print_exc()
                else:
                    errstr += " " * (loc - len(errstr)) + "^"
                    errs.append(err)
                    if self.debug:
                        try:
                            raise err
                        except Exception:  # how to print to terminal
                            traceback.print_exc()
            errstr = " " * 1 + errstr  # TODO: MAKE this use len(commandchar)
            self.send(msg.reply(errstr))
            for i, ex in enumerate(errs):
                self.send(msg.reply(
                    ((str(i + 1) + ": ") if len(e.exs) > 1 else "") + str(ex.__class__.__name__) + ": " + str(ex)))
        except ResultingCallTooLong:
            self.send(msg.reply("Error: Resulting call would be too long!"))
        except Exception as e:  # shouldn't happen... but just in case it does
            self.send(msg.reply(str(e.__class__.__name__) + ": " + str(e)))
            raise

    async def run_parse(self, tree, msg, callback=None, offset=0, preargs=[], outputfilter=False, recursion_limit=0):
        y, off, x = tree[0]
        if y == "pipeline":
            return await self.run_pipeline(x, msg, callback=callback, offset=offset, preargs=preargs,
                                           outputfilter=outputfilter, recursion_limit=recursion_limit-1)
        elif y == "assignment":
            (_, _, [target]), (_, _, x) = x

            try:
                path = target.split(".")
                path.reverse()
                temp = ChainMap(self.env, {"self": self.userspaces[msg.server][msg.nick]})
                while len(path) > 1:
                    temp = temp[path.pop()]
            except KeyError as e:
                raise NameError("Name %s is not defined" % e)

            res = await self.run_pipeline(x, msg, offset=offset, preargs=preargs)  # should never filter assignments

            if len(res) == 1:
                x = res[0].data
            else:
                x = list(map(lambda m: m.data, res))

            temp[path.pop()] = x
            return x

        elif y == "alias":
            (_, _, target), pipeline = x
            self.aliases[target] = pipeline

    async def run_pipeline(self, pipeline, initial: Message, callback=None, offset=0, preargs=[], outputfilter=False, recursion_limit=0):
        cmds_n_args = []
        locs = []
        for (func, args, start) in await self.funcs_n_args(pipeline, initial, offset=offset, preargs=preargs, recursion_limit=recursion_limit):
            cmds_n_args.append((func, initial.reply(
                text=" ".join(map(lambda d: ("{p}{q}{s}{q}".format(p=d.type if isinstance(d, bString) else "", q=d.qtype if isinstance(d, aString) else '', s=d)), args)), data=args)))
            locs.append(start)
        if outputfilter:
            for outfilter in self.outputfilters:
                cmds_n_args.append((outfilter, initial))
        x = self.PipeManager.run_pipe(
            cmds_n_args, loop=None,
            callback=callback, timeout=300)
        res, x = await x
        errs = []
        for err, location in zip(x, locs):
            if isinstance(res, PipeError):
                errs.extend(res.exs)
            elif isinstance(err, SyntaxError) and err.offset is not None:
                errs.append((location + err.offset, err))
            elif isinstance(err, Exception):
                errs.append((location, err))
        if errs:
            raise PipeError(errs)
        return res

    async def do_arg(self, arg, initial, offset=0, preargs=[], recursion_limit=0):
        if recursion_limit <= 0:
            raise RecursionError("recursion limit reached")
        arg_type, loc, s = arg
        if arg_type in ["t_nakedvar", "t_bracketvar"]:
            try:
                path = s.split(".")
                path.reverse()
                x = ChainMap(self.env, {"self": self.userspaces[initial.server][initial.nick]}, self.envs)
                while path:
                    x = x[path.pop()]
                return [x]
            except KeyError as e:
                raise NameError("Name %s is not defined" % e)
        elif arg_type == "backquote":
            res = await self.run_parse(total.parseString(s, parseAll=True), initial, preargs=preargs, offset=loc + offset + 1, recursion_limit=recursion_limit-1)
            x = list(map(lambda m: m.data, res))
            return [x]
        elif arg_type == "doublequote":
            for x in reversed(list(inners.scanString(s))):
                toks, start, end = x
                b = " ".join(
                    str(b).replace('"', '\\"') for b in await self.do_arg(toks[0], initial, offset=offset + loc, preargs=preargs, recursion_limit=recursion_limit-1))
                s = s[:start] + str(b) + s[end:]
            a = aString(s)
            a.quotetype('"')
            return [a]
        elif arg_type == "singlequote":
            a = aString(s)
            a.quotetype("'")
            return [a]
        elif arg_type == "pythonstring":
            [a] = await self.do_arg(s[1], initial, offset=offset+loc, preargs=preargs, recursion_limit=recursion_limit-1)
            b = bString(a)
            b.settype(s[0])
            b.quotetype(a.qtype)
            return [b]
        elif arg_type == "msg_buffer":
            index, name = s.index, s.name
            if index is None:
                index = 1
            else:
                index = int(index)

            if name is None:
                try:
                    return [self.message_buffer[initial.server][initial.params][-index].text]
                except IndexError:
                    raise IndexError("Message buffer index out of range")
            count = 0
            for msg in filter(lambda m: m.nick == name, reversed(self.message_buffer[initial.server][initial.params])):
                count += 1
                if count == index:
                    return [msg.text]
            raise IndexError("Message buffer index out of range")
        elif arg_type == "homedir":
            try:
                path = s.split(".")
                path.reverse()
                x = copy.deepcopy(self.userspaces[initial.server])
                while path:
                    x = x[path.pop()]
                return [x]
            except KeyError as e:
                raise KeyError("No such user: " + str(e))
        elif arg_type == "starred":
            [a] = await self.do_arg(s, initial, offset=offset + loc, preargs=preargs, recursion_limit=recursion_limit-1)
            return [n for n in a]
        elif arg_type == "arg_index":
            index = int(s.index)
            try:
                return [preargs[index]]
            except IndexError:
                raise IndexError("missing arg %s" % index)
        elif arg_type == "arg_range":
            start = None if s.start is None else int(s.start)
            stop = None if s.stop is None else int(s.stop)
            step = None if s.step is None else int(s.step)
            try:
                if isinstance(preargs, (str, bytes)):
                    return [preargs[slice(start, stop, step)]]
                else:
                    return [[q for q in preargs[slice(start, stop, step)]]]
            except IndexError as e:
                raise IndexError(("missing arg %s :" % start) + str(e))
        elif arg_type == "escaped":
            print("escaped", s)
            return [s[1:]]
        else:
            return [s]

    async def do_args(self, args, initial, preargs=[], offset=0, recursion_limit=0):
        rargs = []
        argers = [self.do_arg(x, initial, offset, preargs, recursion_limit=recursion_limit) for x in args]
        x = await asyncio.gather(*argers, return_exceptions=True)
        _, locs, _ = zip(*args)
        errs = []
        for res, location in zip(x, locs):
            if isinstance(res, PipeError):
                errs.extend(res.exs)
            elif isinstance(res, SyntaxError):
                errs.append((location + res.offset + offset, res))
            elif isinstance(res, Exception):
                errs.append((location + offset, res))
            else:
                rargs.extend(res)

        if errs:
            raise PipeError(errs)
        else:
            return rargs

    async def funcs_n_args(self, pipeline, initial, preargs=[], offset=0, count=0, recursion_limit=0):
        count = count
        ret = []
        errs = []
        for _, _, [(_, start, cmd_name), *cmd_args] in pipeline:
            if count > 50:
                raise ResultingCallTooLong()
            if cmd_args:
                try:
                    args = await self.do_args(cmd_args, initial, preargs, offset, recursion_limit=recursion_limit)
                except PipeError as p:
                    errs.extend(p.exs)
            else:
                args = []

            if cmd_name in self.commands:
                if not errs:
                    func = self.commands[cmd_name]
                    ret.append((func, args, start + offset))
                    count += 1
            elif cmd_name in self.aliases:
                if not errs:
                    _, _, pip = pipline.parseString(self.aliases[cmd_name], parseAll=True)[0]
                    try:
                        for func_, args_, _ in await self.funcs_n_args(pip, initial, preargs=args,
                                                                       offset=offset + start, count=count + 1, recursion_limit=recursion_limit-1):
                            ret.append((func_, args_, start + offset))
                            count += 1
                    except PipeError as e:
                        errs.extend([(start, err) for _, err in e.exs])

            else:
                errs.append((offset + start, NameError("Unrecognised Command '%s'" % cmd_name)))

        if errs:
            raise PipeError(errs)
        return ret

    @staticmethod
    def from_config(filename):
        import json, codecs
        json_config = codecs.open(filename, 'r', 'utf-8-sig')
        config = json.load(json_config)
        loop = asyncio.get_event_loop()

        kws = {}
        if "debug" in config:
            kws['debug'] = config['debug']

        if "aliasfile" in config:
            kws['aliasfile'] = config['aliasfile']

        if 'envfile' in config:
            kws['envfile'] = config['envfile']

        if 'userspacefile' in config:
            kws['userspacefile'] = config['userspacefile']

        bot = Pyperbot(loop=loop, **kws)

        if "apikeys" in config:
            for api, key in config["apikeys"].items():
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


if __name__ == "__main__":
    log = logging.getLogger("pyperbot")
    log.setLevel(logging.DEBUG)

    ch = ShitHandler()

    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)
    log.addHandler(ch)

    from sys import argv

    bot = Pyperbot.from_config(argv[1])
    try:
        if '-i' in argv:
            from pyperbot.shell import interactive_shell

            asyncio.ensure_future(interactive_shell(bot))
        bot.run()
    except KeyboardInterrupt:
        bot.sync()
