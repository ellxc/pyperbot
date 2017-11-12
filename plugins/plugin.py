import sys
sys.path.append("C:\\seval-master")
import seval
from piping import PipeClosed
from wrappers import plugin, command, classcommand, event, pipeinable_command, complexcommand

from collections import ChainMap

@plugin
class foo():

    @pipeinable_command
    def strfrmt(self, args, each):
        print(args)
        return args.reply(args.text.format(each.text))

    @pipeinable_command
    def strfrmt2(self, args, each):
        print(args)
        yield args.reply(args.text.format(each.text))
        yield args.reply(args.text.format(each.text))

    @command
    def arger(self, each):
        yield each.reply(each.args)

    @command
    def two(self, msg):
        return msg.reply(2)

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
        self.sv = seval.Seval()

    @command
    def echo(self, msg):
        return msg.reply(msg.text)

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

    @complexcommand(">")
    @complexcommand
    async def seval(self, args, inpipe, outpipe):
        called = False
        try:
            while 1:
                x = await inpipe.recv()
                response, env = self.sv.parse_string(args.text, ChainMap(self.bot.env, {"msg": x}))
                print("env",env)
                self.bot.env.update(env)
                called = True
                for r in response:
                    outpipe.send(args.reply(repr(r)))
        except PipeClosed:
            if not called:
                response, env = self.sv.parse_string(args.text, self.bot.env)
                print("env", env)
                self.bot.env.update(env)
                for r in response:
                    outpipe.send(args.reply(repr(r)))
        finally:
            outpipe.close()
            inpipe.close()



    @pipeinable_command
    def rev(self, msg):
        return msg.reply(msg.data[::-1])
