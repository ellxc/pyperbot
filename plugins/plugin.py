from time import sleep
import asyncio
from time import sleep
from collections import ChainMap
from piping import PipeClosed
from pyperbot import funcnotdef
from pyperparser import total
from seval import parse_string
from util import schedthreadedfunc, schedproccedfunc
from wrappers import plugin, command, classcommand, pipeinable_command, complexcommand


@plugin
class foo():

    @pipeinable_command
    def strfrmt(self, args, each):
        # formats = len(list(string.Formatter().parse(args.line)))
        return args.reply(args.line.format(*each.data))

    @pipeinable_command
    def strfrmt2(self, args, each):
        yield args.reply(args.line.format(each.data))
        yield args.reply(args.line.format(each.data))

    @command
    def arger(self, each):
        yield each.reply(each.args)

    @command
    def two(self, msg):
        return msg.reply(2)

    @command
    async def shitsleep(self, msg):
        await schedthreadedfunc(sleep, 5)
        return msg.reply("I waited!")

    @command
    async def shitsleep2(self, msg):
        await schedproccedfunc(sleep, 5)
        return msg.reply("I waited!")

    @command
    async def sleep(self, msg):
        await asyncio.sleep(2)
        return msg.reply(2)

    @command
    async def sleep2(self, msg):
        await asyncio.sleep(2)
        yield msg.reply(2)
        yield msg.reply(2)

    @pipeinable_command
    def twice(self, args, msg):
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

    def __init__(self, bot):
        self.bot = bot

    @command
    def echo(self, msg):
        return msg.reply(data=msg.args, text=" ".join(map(str, msg.args)))

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

    async def funcs_n_args(self, pipeline, initial):
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
                raise funcnotdef(0, cmd_name)

    @complexcommand
    async def xargs(self, args, inpipe, outpipe):
        try:
            strpipe = False
            if args.args and args.args[0] == '-s':
                strpipe = True
                pipeline = args.args[1]
            else:
                pipeline = [args.args]
            while 1:
                x = await inpipe.recv()
                print("got ", x)
                if strpipe:
                    print("new style")
                    parse = total.parseString(pipeline.format(*x.data))
                    print(parse)
                    await self.bot.run_parse(parse, x, callback=outpipe.send)
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

    @complexcommand(">")
    @complexcommand
    async def seval(self, args, inpipe, outpipe):
        called = False
        try:
            while 1:
                x = await inpipe.recv()
                response, _ = parse_string(ChainMap(self.bot.env, {"msg": x}), args.line)
                called = True
                outpipe.send(args.reply(data=response, text=repr(response)))
        except PipeClosed:
            if not called:
                response, _ = parse_string(ChainMap(self.bot.env, {"msg": args}), args.line)
                # del env["msg"]
                # self.bot.env = dict(env)

                outpipe.send(args.reply(data=response, text=repr(response)))
        finally:
            outpipe.close()
            inpipe.close()

    @pipeinable_command
    def iterate(self, msg):
        for x in msg.data:
            yield msg.reply(x)

    @pipeinable_command
    def rev(self, msg):
        return msg.reply(msg.data[::-1])
