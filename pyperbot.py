# coding=utf-8
import asyncio
from asyncio.coroutines import _format_coroutine
import traceback
from Message import Message
import logging
from client import IrcClient
from events import EventManager
from parse4 import parse
import inspect
import importlib
import os
from piping import PipeManager
import pyparsing as pyp
from wrappers import plugin
from collections import defaultdict
from threading import Event
import time

class envnotdef(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex

class Pyperbot:
    def __init__(self, loop :asyncio.AbstractEventLoop):
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
        self.em.register_handler("command", self.handle_command)

        self.env = {"baz": "quux", "a": "x", "x": "b", "foo": {"bar": "baz"}}

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
                temp.nick = self.servers[message.server].nick
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
        print(handlers)
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
                print("found a command!" + name)
                for word in func._commands:
                    self.commands[word] = func


    def parse_command(self, msg, first=False, offset = 0, checkonly=False):
        if first:
            text = msg.text[1:]
        else:
            text = msg.text




        def get_from_env(thing, loc):
            try:
                path = thing.split(".")
                path.reverse()
                print(path)
                x = self.env
                while path:
                    x = x[path.pop()]
                return x
            except KeyError as e:
                print("err", loc)
                raise envnotdef(loc+offset, e)




        def str_insert(orig, inp, start, end):
            return orig[:start] + " ".join(map(str, inp)) + orig[end:]



        t_word = pyp.Regex(r'([^ |\'\"\\]|\\\\)+')
        t_bracketvar = pyp.nestedExpr('${', '}', content=pyp.CharsNotIn("{}"),
                                      ignoreExpr=pyp.quotedString ^ pyp.nestedExpr('{', '}'))\

        t_nakedvar = pyp.Suppress('$') + pyp.CharsNotIn(" )([]:+=")
        cmd_buffer = pyp.Regex(r"\S*\^(\^+|\d+)?") + pyp.WordEnd()
        cmd_buffer.addParseAction(lambda s, l, t: "previous message: " + t[0], callDuringTry=False)
        t_tilde = pyp.Suppress('~') + t_word
        t_tilde.addParseAction(lambda s, l, t: "home of " + t[0], callDuringTry=False)
        singlequote = pyp.QuotedString(quoteChar="'", escChar="\\")
        doublequote = pyp.QuotedString(quoteChar='"', escChar='\\')
        backquote = pyp.QuotedString(quoteChar='`', escChar='\\')

        inners = pyp.MatchFirst((backquote ^ doublequote, t_bracketvar, t_nakedvar, t_tilde))
        t_var = (t_bracketvar | t_nakedvar)
        escaped = pyp.Combine(pyp.Suppress("\\") + pyp.Or(("'", '"', '`')))
        cmd_arg = pyp.MatchFirst((cmd_buffer, t_var, singlequote, doublequote, backquote, escaped, t_tilde, t_word))
        cmd_name = t_word("cmd_name").setParseAction(lambda locn, tokens: (locn, tokens[0]))
        simple_command = pyp.Group(cmd_name + pyp.Group(pyp.ZeroOrMore(cmd_arg))("args"))
        pipeline = pyp.Group(pyp.delimitedList(simple_command, '|'))("pipeline") # .addParseAction(lambda s, l, t: [x for x in t])
        pipeline2 = pyp.Group(pyp.delimitedList(simple_command, '|'))("pipeline2") # .addParseAction(lambda s, l, t: [x for x in t])
        t_assignment_word = t_word.setResultsName('target')
        assignment = t_assignment_word + pyp.Suppress('=') + pipeline.copy()


        def test(s, l, t):
            print("test!")
            print(s, l, t)
            print(t[0])
            print(t[0][0])
            print([(func, args) for func, args in t[0]])
            try:
                temp = asyncio.new_event_loop()
                temp.run_until_complete(self.PipeManager.run_pipe(
                    [(self.commands[func], msg.to_args(text=" ".join(args), args=args)) for func, args in t[0]],
                    loop=temp,
                    callback=self.send))
                temp.stop()
            except Exception as e:
                print("fuckd")
                print(e)
            return t

        

        def funcs_n_args(t, first=True, baz=None):
            a = []
            locs = []
            for (loc, func), args in t:
                print((loc, func), args, t, first)
                print(loc)
                print(func)
                print(args)
                print(t)
                if func in self.commands:
                    a.append((self.commands[func], msg.to_args(text=" ".join(map(str, args)), args=[x for x in args])))
                    print("adding loc: ", loc)
                    locs.append(loc)
                elif func in self.aliases:
                    try:
                        first = True
                        for func2, args2 in funcs_n_args(pipeline.parseString(self.aliases[func], parseAll=True)[0], first=False, baz=loc)[0]:
                            print(func2, args2)
                            if first:
                                args2.args += [x for x in args]
                                first = False
                            a.append((func2, args2))
                            locs.append(loc)
                            print(baz)
                    except envnotdef as e:
                        if first:
                            self.send(msg.reply(" "*(loc+offset)+"^"))
                            self.send(msg.reply(str(e.ex)+" is not defined"))
                        raise Exception
                else:
                    print("loc", loc)
                    self.send(msg.reply(" "*(loc+offset)+"^"))
                    self.send(msg.reply("UnKnown Command: " + func))
                    raise Exception
                first_func = False
            return a, locs


        def pipaa(s, l, t, send=True):
            temp = asyncio.new_event_loop()
            cmds_n_args, locs = funcs_n_args(t[0])#[(self.commands[func], msg.to_args(text=" ".join(map(str, args)), args=args)) for (loc, func), args in t[0]]
            print(cmds_n_args, locs)
            x = self.PipeManager.run_pipe(
                cmds_n_args, loop=temp,
                callback=self.send if first and send else None)
            res, x = temp.run_until_complete(x)

            errstr = ""
            errs = []
            for err, location in zip(x, locs):
                if isinstance(err, Exception):
                    print(err, location)
                    traceback.print_exc()
                    errstr += " "*(location-len(errstr)+1)+"^"
                    errs.append(err)

            if errstr:
                self.send(msg.reply(errstr))
                for i, e in enumerate(errs):
                    self.send(msg.reply(((str(i+1)+": ") if len(errs) > 1 else "") +str(e.__class__.__name__) + ": " + str(e)))
                raise e


            if res:
                return list(map(lambda m: m.data, res))

        def ass(s, l, t):
            print("assignment", t[0], " = ", t[1])
            self.env[t[0]] = t[1]
            return t[1]

        def assign(s, l, t):
            res = pipaa(s, l, [t[1]], send=False)

            if res is not None and len(res) == 0:
                x = res[0]
            else:
                x = res

            self.env[t[0]] = x

            print("assignment", t[0], " = ", x)
            return x

        def aliaser(s, l, t):
            print(s, l, t)
            try:
                self.parse_command(msg.reply(t[1]), offset=offset + l, checkonly=True) # pipeline.parseString(t[1], parseAll=True)
            except pyp.ParseException:
                raise
            except Exception: # if this happened then that is okay
                pass
            self.aliases[t[0]] = t[1].strip()


        inners = pyp.MatchFirst((backquote, t_var, t_tilde))

        def doinner(s, l, t):
            inp = t[0]
            for x in reversed(list(inners.scanString(inp))):
                toks, start, end = x
                inp = str_insert(inp, toks, start, end)

            return inp

        # def backers(s, l, t):
        #     try:
        #         self.parse_command(msg.reply(t[0]), offset=offset + l)
        #     except envnotdef as e:
        #         if first:
        #             self.send(msg.reply(" "*(e.col+offset) + "^"))
        #             self.send(msg.reply(str(e.__class__.__name__) + ": " + e.msg))
        #         raise



        backquote.addParseAction(lambda s, l, t: self.parse_command(msg.reply(t[0]), offset=offset + l + 1, checkonly=True), callDuringTry=False)
        t_alias_word = t_word("alias_target")
        alias = pyp.Suppress(pyp.Literal("alias")) + t_alias_word + pyp.Suppress('=') + pyp.restOfLine()
        alias.addParseAction(aliaser)
        pipeline2 = pipeline.copy()
        total = (alias | assignment | pipeline2)

        try:
            total.parseString(text, parseAll=True)
        except pyp.ParseException as e:
            if first:
                self.send(msg.reply(" "*(e.col+offset) + "^"))
                self.send(msg.reply(str(e.__class__.__name__) + ": " + e.msg))
            raise

        if checkonly:
            return
        backquote.setParseAction(lambda s, l, t: self.parse_command(msg.reply(t[0]), offset=offset + l + 1),
                                 callDuringTry=False)
        t_nakedvar.addParseAction(lambda s, l, t: get_from_env(t[0], l), callDuringTry=False)
        t_bracketvar.addParseAction(lambda s, l, t: get_from_env(t[0][0], l), callDuringTry=False)
        doublequote.addParseAction(doinner, callDuringTry=False)
        assignment.addParseAction(assign, callDuringTry=False)
        pipeline2.addParseAction(pipaa, callDuringTry=False)
        try:
            x = total.parseString(text, parseAll=True)
        except envnotdef as e:
            if first:
                self.send(msg.reply(" "*(e.loc+offset) + "^"))
                self.send(msg.reply(str(e.ex)+" is not defined"))
            else:
                print("got an envdef in stack")
            raise
        print(msg.text, "->", x)
        return x


    def handle_command(self, msg):
        try:
            first = msg.text[1:].split()[0].split("|")[0]
            if first in self.aliases or first in self.commands:
                self.parse_command(msg, first=True, offset=1)
        except pyp.ParseException:
            pass
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
    log = logging.getLogger("pyperbot")
    log.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()

    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
