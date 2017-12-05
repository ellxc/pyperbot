import copy
from collections import ChainMap

from seval.seval import parse_string

from pyperbot.piping import PipeClosed
from pyperbot.wrappers import plugin, complexcommand


@plugin
class Seval:
    @complexcommand(">")
    @complexcommand
    async def seval(self, args, inpipe, outpipe):
        """this is a sandboxed python interpreter, it is mostly complete"""
        called = False
        try:
            while 1:
                x = await inpipe.recv()
                response, _ = parse_string(
                    ChainMap(self.bot.env, {"msg": x}, {"self": self.bot.userspaces[args.server][args.nick]} if args.server in self.bot.userspaces else {},
                             copy.deepcopy(self.bot.userspaces[args.server]) if args.server in self.bot.userspaces else {}, self.bot.envs), args.text)
                called = True
                if response:
                    for r in response:
                        outpipe.send(args.reply(data=r, str_fn=repr))
        except PipeClosed:
            if not called:
                response, _ = parse_string(
                    ChainMap(self.bot.env, {"msg": args.reply()}, {"self": self.bot.userspaces[args.server][args.nick]} if args.server in self.bot.userspaces else {},
                             copy.deepcopy(self.bot.userspaces[args.server]) if args.server in self.bot.userspaces else {}, self.bot.envs), args.text)
                if response:
                    for r in response:
                        outpipe.send(args.reply(data=r, str_fn=repr))
        finally:
            outpipe.close()
            inpipe.close()
