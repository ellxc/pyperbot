import asyncio
from collections import ChainMap
from time import sleep

from piping import PipeClosed
from pyperparser import total

try:
    from seval import parse_string
except:
    pass
from util import schedthreadedfunc, schedproccedfunc, CommandNotDefined
from wrappers import plugin, command, classcommand, pipeinable_command, complexcommand, regex, outputfilter, cron, \
    unload, onload, env
import urllib.parse
import urllib.response
import urllib.request
import datetime
import copy


@plugin
class foo():
    @pipeinable_command
    def strfrmt(self, args, each):
        # formats = len(list(string.Formatter().parse(args.line)))
        return args.reply(text=args.text.format(*each.data))

    @pipeinable_command
    def strfrmt2(self, args, each):
        yield args.reply(text=args.text.format(each.data))
        yield args.reply(text=args.text.format(each.data))

    @command
    def arger(self, args):
        yield args.reply(args.data)

    @command
    def two(self, msg):
        return msg.reply([2])

    @command
    async def shitsleep(self, msg):
        await schedthreadedfunc(sleep, 5)
        return msg.reply(["I waited!"])

    @command
    async def shitsleep2(self, msg):
        await schedproccedfunc(sleep, 5)
        return msg.reply(["I waited!"])

    @command
    async def sleep(self, msg):
        await asyncio.sleep(2)
        return msg.reply([2])



    @pipeinable_command
    async def twice(self, args, msg):
        print("twice!", msg.data)
        yield msg
        yield msg

    @classcommand
    class count:
        def __init__(self, args, inpipe, outpipe):
            self.args = args
            self.outpipe = outpipe
            self.f = 0

        def __call__(self, msg):
            self.f += 1

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.outpipe.send(self.args.reply("got {} messages".format(self.f)))


@plugin
class bar():
    def __init__(self, bot, config):
        self.bot = bot

    @command
    def echo(self, msg):
        return msg

    @command(admin=True)
    def admin(self, msg):
        return msg.reply(["derp"])

    @command(admin=True)
    def exit(self, msg):
        self.bot.loop.stop()

    @command
    def error(self, msg):
        raise Exception("foo bar baz")

    @command
    def error2(self, msg):
        raise AssertionError("foo bar baz")

    @command
    def quux(self, args):
        print("asd!!!", args.args)
        pass

    async def funcs_n_args(self, pipeline, initial, preargs=[]):
        # print("pipeline >>", pipeline)
        count = 0
        first = True
        for [cmd_name, *cmd_args] in pipeline:
            print(cmd_name, cmd_args)
            # if count > 50:
            #     raise toomany()
            if first:
                first = False
                args = cmd_args + (initial.data or [])
                # text = [str(t) for t in args.args[1:]]
            else:
                args = cmd_args

            if cmd_name in self.bot.commands:
                print("got here")
                func = self.bot.commands[cmd_name]
                yield (func, initial.to_args(args=args, line=" ".join(map(str, cmd_args))))
                count += 1
                print("got here2")
            elif cmd_name in self.bot.aliases:
                first = True
                async for func_, args_, text_, _ in self.bot.funcs_n_args(self.bot.aliases[cmd_name], initial,
                                                                          preargs=args, offset=0, count=count + 1):
                    # if first:
                    #     args_ += args
                    #     text_ += text
                    #     first = False
                    yield (func_, initial.to_args(args=args_, line=" ".join(text_)))
                    count += 1
            else:
                raise CommandNotDefined(0, cmd_name)

    @complexcommand
    async def xargs(self, args, inpipe, outpipe):
        try:
            strpipe = False
            if args.data and args.data[0] == '-s':
                strpipe = True
                pipeline = args.data[1]
            else:
                pipeline = [args.data]
            while 1:
                x = await inpipe.recv()
                print("got ", x)
                if strpipe:
                    print("new style")
                    parse = total.parseString(pipeline)
                    print(parse)
                    await self.bot.run_parse(parse, x, callback=outpipe.send, preargs=x.data)
                else:
                    print("old style")
                    temp = []
                    async for shit in self.funcs_n_args(pipeline, x):
                        temp.append(shit)
                    await self.bot.PipeManager.run_pipe(temp, callback=outpipe.send)
        except PipeClosed:
            pass
        finally:
            outpipe.close()
            inpipe.close()

    @env("karma")
    def k(self):
        return {"Elliot": 5}


    @complexcommand(">")
    @complexcommand
    async def seval(self, args, inpipe, outpipe):
        called = False
        try:
            while 1:
                x = await inpipe.recv()
                response, _ = parse_string(
                    ChainMap(self.bot.env, {"msg": x}, {"self": self.bot.userspaces[args.server][args.nick]},
                             copy.deepcopy(self.bot.userspaces[args.server]), self.bot.envs), args.text)
                called = True
                if response:
                    outpipe.send(args.reply(data=response, str_fn=lambda x: "; ".join(map(repr, x))))
        except PipeClosed:
            if not called:
                response, _ = parse_string(
                    ChainMap(self.bot.env, {"msg": args.reply()}, {"self": self.bot.userspaces[args.server][args.nick]},
                             copy.deepcopy(self.bot.userspaces[args.server]), self.bot.envs), args.text)
                if response:
                    outpipe.send(args.reply(data=response, str_fn=lambda x: "; ".join(map(repr, x))))
        finally:
            outpipe.close()
            inpipe.close()

    @pipeinable_command
    def iterate(self, args, msg):
        for x in msg.data:
            yield msg.reply([x])

    @complexcommand
    async def cat(self, initial, inpipe, outpipe):
        cot = []
        try:
            while 1:
                x = await inpipe.recv()
                cot.append(x.data)
        except PipeClosed:
            outpipe.send(initial.reply(cot))
        finally:
            outpipe.close()
            inpipe.close()

    @pipeinable_command
    def rev(self, args, msg):
        return msg.reply(msg.data[::-1])


@plugin
class test:
    @onload
    def load(self):
        print("plugin loaded!!!1!!one!!")

    @unload
    def uload(self):
        print("plugin unloaded!!1one11!!")

    @cron("*/2 * * * *")
    def fizz(self):
        print("fizz", datetime.datetime.now())

    @cron("*/3 * * * *")
    def buzz(self):
        print("buzz", datetime.datetime.now())

    @regex(r"what")
    def regg(self, msg, match):
        print(match)

    @complexcommand
    async def timeit(self, initial, inpipe, outpipe):
        tim = initial.timestamp
        try:
            while 1:
                x = await inpipe.recv()
                outpipe.send(x)
        except PipeClosed:

            outpipe.send(initial.reply([(datetime.datetime.now() - tim).total_seconds()]))
        finally:
            outpipe.close()
            inpipe.close()

    @outputfilter
    async def spam(self, initial, inpipe, outpipe):
        spam = []
        try:
            while 1:
                x = await inpipe.recv()
                spam.append(x)
                if len(spam) < 4:
                    outpipe.send(x)
        except PipeClosed:
            if len(spam) > 4:
                data = {'f:1': '\n'.join(m.text for m in spam)}
                response = await schedthreadedfunc(urllib.request.urlopen, urllib.request.Request('http://ix.io',
                                                                                                  urllib.parse.urlencode(
                                                                                                      data).encode(
                                                                                                      'utf-8')))
                response = response.read().decode()
                outpipe.send(initial.reply(text="spam detected! here is the output: %s" % response))
            elif len(spam) == 4:
                outpipe.send(spam[-1])
        finally:
            outpipe.close()
            inpipe.close()
