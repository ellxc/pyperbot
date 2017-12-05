from pyperbot.piping import PipeClosed
from pyperbot.wrappers import plugin, command, pipeinable_command, complexcommand
from itertools import chain
from collections import Iterable, Mapping


@plugin
class Core:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @complexcommand
    async def tail(self, initial, inpipe, outpipe):
        if initial.data:
            level = int(initial.data[0])
        else:
            level = 1

        cot = []
        try:
            while 1:
                x = await inpipe.recv()
                cot.append(x)
        except PipeClosed:
            for m, _ in zip(reversed(cot), range(level)):
                outpipe.send(m)
        finally:
            outpipe.close()
            inpipe.close()

    @complexcommand
    async def head(self, initial, inpipe, outpipe):
        if initial.data:
            level = int(initial.data[0])
        else:
            level = 1
        try:
            while 1:
                x = await inpipe.recv()
                if level > 0:
                    outpipe.send(x)
                    level -= 1
                else:
                    outpipe.close()
        except PipeClosed:
            pass
        finally:
            outpipe.close()
            inpipe.close()

    @command
    def nicks(self, msg):
        nicks = list(self.bot.clients[msg.server].nicks[msg.params])
        return msg.reply(data=nicks)

    @pipeinable_command
    def strfrmt(self, args, each):
        """will format the string with any passed in data"""
        if isinstance(each.data, Mapping):
            return each.reply(text=args.text.format(**each.data))
        if isinstance(each.data, Iterable) and not isinstance(each.data, (str, bytes)):
            return each.reply(text=args.text.format(*each.data))
        return each.reply(text=args.text.format(each.data))

    @pipeinable_command
    def str(self, args, each):
        return each.reply(text=str(each.data if each.data is not None else each.text))

    @command
    def echo(self, msg):
        """immediately echoes the arguments"""
        return msg

    def unwrap(self, x, level):
        for y in x:
            if level == 1:
                yield y
            else:
                for z in self.unwrap(y, level-1):
                    yield z

    @pipeinable_command
    def iterate(self, args, msg):
        """iterate through msg.data and create a new message for each one"""
        if args.data:
            level = int(args.data)
        else:
            level = 1

        for x in self.unwrap(msg.data, level):
            yield msg.reply([x])

    @pipeinable_command
    def flatten(self, args, msg):
        return msg.reply(list(chain.from_iterable(msg.data)))


    @complexcommand
    async def cat(self, initial, inpipe, outpipe):
        """combines all incoming data"""
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

    @complexcommand
    async def timeit(self, initial, inpipe, outpipe):
        """passes on all messages and then how long it took from initialisation to completion"""
        tim = initial.timestamp
        try:
            while 1:
                x = await inpipe.recv()
                outpipe.send(x)
        except PipeClosed:
            outpipe.send(initial.reply([(tim.now() - tim).total_seconds()]))
        finally:
            outpipe.close()
            inpipe.close()
