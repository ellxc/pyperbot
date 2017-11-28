from wrappers import plugin, complexcommand

try:
    from seval import parse_string
except:
    pass
from collections import ChainMap
from piping import PipeClosed
import copy


@plugin
class seval:
    @complexcommand(">")
    @complexcommand
    async def seval(self, args, inpipe, outpipe):
        """this is a sandboxed python interpreter, it is mostly complete"""
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
