# coding=utf-8
import asyncio
import importlib
import inspect
import logging
import os
import traceback

import pyparsing as pyp
from pyparsing import ParseException

from Message import Message
from client import IrcClient
from events import EventManager
from piping import PipeManager
from pyperparser import total, inners


class missingarg(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex

    def __str__(self):
        return self.ex

class envnotdef(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex


class funcnotdef(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex


class piperror(Exception):
    def __init__(self, errstr, exs):
        self.errstr = errstr
        self.exs = exs


class toomany(Exception):
    pass


class Pyperbot:
    def __init__(self, loop: asyncio.AbstractEventLoop, shell=True):
        self.loop = loop
        self.clients = {}
        self.em = EventManager(loop=loop)
        self.PipeManager = PipeManager()
        self.plugins = {}
        self.triggers = {}
        self.commands = {}
        self.aliases = {}
        self.regexes = {}
        self.cron = {}
        self.em.register_handler("PRIVMSG",
                              lambda message: a.em.fire_event("command", msg=message) if message.text.startswith(
                                  "#") else None)
        self.em.register_handler("command", lambda msg: asyncio.ensure_future(self.parse_msg(msg), loop=self.loop))
        self.env = {"baz": "quux", "a": "x", "x": "b", "foo": {"bar": "baz"}}
        self.userspaces = {}

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

    def send(self, message):
        if message.server in self.clients:
            self.clients[message.server].send(message)
            if 0 and message.command == "PRIVMSG":  # TODO: buffers
                temp = message.copy()
                temp.nick = self.clients[message.server].nick
                self.message_buffer[message.server][message.params].appendleft(temp)
        else:
            raise Exception("no such server: " + message.server)

    def load_plugin_file(self, plugin):
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
                    self.plugins[name] = Class()
                    self.load_plugin(self.plugins[name])
        else:
            temp = importlib.machinery.SourceFileLoader(plugin, os.path.dirname(
                os.path.abspath(__file__)) + "/plugins/" + plugin + ".py").load_module()
            found = False
            for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
                handlers.append(Class)
                self.plugins[name] = Class(self)
                self.load_plugin(self.plugins[name])
                found = True
            if not found:
                raise Exception("no such plugin to load or file did not contain a plugin")
        return handlers

    def load_plugin(self, plugin):
        print("loading plugin: " + plugin.__class__.__name__)
        for name, func in inspect.getmembers(self.plugins[plugin._name]):
            if hasattr(func, "_crons"):
                pass
            if hasattr(func, "_events"):
                pass
            if hasattr(func, "_triggers"):
                pass
            if hasattr(func, "_regexes"):
                pass
            if hasattr(func, "_commands"):
                for word in func._commands:
                    self.commands[word] = func

    async def parse_msg(self, msg):
        try:
            x = total.parseString(msg.text[1:], parseAll=True)
            print(msg.text[1:], "->", x)
            await self.run_parse(x, msg, callback=self.send)
        except ParseException as e:
            self.send(msg.reply(" " * (e.col + 1) + "^"))
            self.send(msg.reply(str(e.__class__.__name__) + ": " + e.msg))
        except envnotdef as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply(str(e.ex) + " is not defined"))
        except funcnotdef as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply("function " + str(e.ex) + " is not defined"))
        except piperror as e:
            self.send(msg.reply(" " * 1 + e.errstr))
            for i, ex in enumerate(e.exs):
                self.send(msg.reply(
                    ((str(i + 1) + ": ") if len(e.exs) > 1 else "") + str(ex.__class__.__name__) + ": " + str(ex)))
                try:
                    raise ex
                except Exception:
                    traceback.print_exc()
        except toomany as e:
            self.send(msg.reply("Error: Resulting call would be too long!"))
        except missingarg as e:
            self.send(msg.reply(" " * (e.loc + 1) + "^"))
            self.send(msg.reply("MissingArg: " + e.ex))
        except Exception as e:
            # self.send(msg.reply(" " * (e.col + 1) + "^"))
            self.send(msg.reply(str(e.__class__.__name__) + ": " + str(e)))

    async def run_parse(self, tree, msg, callback=None, offset=0):
        y, off, x = tree[0]
        if y == "pipeline":
            return await self.run_pipeline(x, msg, callback=callback, offset=offset)
        elif y == "assignment":
            (_, _, [target]), (_, _, x) = x
            res = await self.run_pipeline(x, msg, offset=offset)

            if res is not None and len(res) == 1:
                x = res[0].data
            else:
                x = list(map(lambda m: m.data, res))

            try:
                path = target.split(".")
                path.reverse()
                temp = self.env
                while len(path) > 1:
                    temp = temp[path.pop()]
                temp[path.pop()] = x
                return x
            except KeyError as e:
                raise envnotdef(offset, e)

        elif y == "alias":
            (_, _, target), (_, _, pipeline) = x
            self.aliases[target] = pipeline

    async def run_pipeline(self, pipeline, initial, callback=None, offset=0):
        cmds_n_args = []
        locs = []
        async for (func, args, text, start) in self.funcs_n_args(pipeline, initial, offset=offset):
            cmds_n_args.append((func, initial.to_args(line=" ".join(map(str, text)), args=args)))
            locs.append(start)
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
                x = self.env
                while path:
                    x = x[path.pop()]
                return [[x, str(x), loc]]
            except KeyError as e:
                raise envnotdef(loc + offset, e)
        elif arg_type == "backquote":
            res = await self.run_parse(total.parseString(s, parseAll=True), initial, offset=loc + offset)
            x = list(map(lambda m: m.data, res))
            xs = list(map(lambda m: str(m.data), res))
            return [[x, xs, loc]]
        elif arg_type == "doublequote":
            for x in reversed(list(inners.scanString(s))):
                toks, start, end = x
                b = " ".join(
                    str(b) for b, _, _ in await self.do_arg(toks[0], initial, offset=offset + loc, preargs=preargs))
                s = s[:start] + str(b) + s[end:]
            return [[s, '"' + s + '"', loc]]
        elif arg_type == "singlequote":
            return [[s, "'" + s + "'", loc]]
        elif arg_type == "homedir":
            pass
        elif arg_type == "starred":
            [[a, b, loc]] = await self.do_arg(s, initial, offset=offset + loc)
            return [[n, str(n), loc] for n in a]
        elif arg_type == "back_index":
            index = int(s.index)
            try:
                return [[preargs[index], str(preargs[index]), loc]]
            except IndexError as e:
                print("fuck", preargs, index)
                raise missingarg(loc, "missing arg no:%s" % index)
        elif arg_type == "back_range":

            # if not preargs:
            #     raise Exception("this pipeline takes a parameter!")
            print("range", s)
            start = None if s.start is None else int(s.start)
            stop = None if s.stop is None else int(s.stop)
            step = None if s.step is None else int(s.step)
            try:
                # got a range

                # if a > len(preargs) or b > len(preargs):
                #     raise IndexError("This pipline needs atleast %s params!" % s[1])  #TODO make this use a custom error with location
                return [[q, str(q), loc] for q in preargs[slice(start, stop, step)]]
            except IndexError as e:
                raise missingarg(loc, "missing arg no:%s" % start)
        else:
            return [[s, s, loc]]

    async def funcs_n_args(self, pipeline, initial, preargs=[], offset=0, count=0):
        count = count
        for _, _, [(_, start, cmd_name), *cmd_args] in pipeline:
            if count > 50:
                raise toomany()

            args = []
            text = []

            argers = [self.do_arg(x, initial, offset, preargs) for x in cmd_args]
            for shit in await asyncio.gather(*argers):
                for arg, s, loc in shit:
                    args.append(arg)
                    text.append(s)

            if cmd_name in self.commands:
                func = self.commands[cmd_name]
                yield (func, args, text, start + offset)
                count += 1
            elif cmd_name in self.aliases:
                first = True
                try:
                    async for func_, args_, text_, _ in self.funcs_n_args(self.aliases[cmd_name], initial, preargs=args,
                                                                          offset=offset + start, count=count + 1):
                        yield (func_, args_, text_, start + offset)
                        count += 1
                except missingarg as e:
                    raise missingarg(e.loc, e.ex + " for alias " + cmd_name)
            else:
                raise funcnotdef(offset + start, cmd_name)

    def handle_command(self, msg):
        try:
            # first = msg.text[1:].split()[0].split("|")[0]
            # if first in self.aliases or first in self.commands:
                self.parse_command(msg, first=True, offset=1)
        except pyp.ParseException:
            traceback.print_exc()
        except envnotdef as e:
            print("env error escaped!")
        except Exception as e:
            traceback.print_exc()
            # no need to send back to channel



        # x = [(self.commands[func], msg.to_args(text=" ".join(args), args=args)) for func, args in cmd]
        # def err(ex: Exception):
        #     self.send(msg.reply("Error: "+str(ex)))
        #
        #
        # self.loop.create_task(self.PipeManager.run_pipe(x, callback=self.send, err_callback=err))

def throw(e):
    raise e

if __name__ == "__main__":
    from logging import Handler


    class shitHandler(Handler):
        """
        A handler class which writes logging records, appropriately formatted,
        to a stream. Note that this class does not close the stream, as
        sys.stdout or sys.stderr may be used.
        """

        def __init__(self):
            Handler.__init__(self)

        def flush(self):
            pass

        def emit(self, record):
            print(self.format(record))

    log = logging.getLogger("pyperbot")
    log.setLevel(logging.DEBUG)

    ch = shitHandler()

    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)
    log.addHandler(ch)

    pw = open("pw").readline()

    loop = asyncio.get_event_loop()
    a = Pyperbot(loop=loop)
    a.load_plugin_file("plugin")
    a.connect_to("kentirc", "irc.cs.kent.ac.uk", 6697, ssl=True, username="ec486", password=pw, nick="pyperbot",
                 channels=["#bottesting"])

    a.em.register_handler("CTCP:HELLO", lambda **kwargs: print("wot"))

    loop.run_forever()
