import copy
from collections import ChainMap
from seval.global_env import globalenv
from dateutil import parser
globalenv.update(dateparse=parser.parse)
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
                response, _ = parse_string(self.bot.get_env(x), args.text)
                called = True
                if response:
                    for r in response:
                        outpipe.send(args.reply(data=r, str_fn=repr))
        except PipeClosed:
            if not called:
                response, _ = parse_string(self.bot.get_env(args.reply()), args.text)
                if response:
                    for r in response:
                        outpipe.send(args.reply(data=r, str_fn=repr))
        finally:
            outpipe.close()
            inpipe.close()
