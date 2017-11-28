from piping import PipeClosed
from wrappers import plugin, command, pipeinable_command, complexcommand


@plugin
class core:
    @pipeinable_command
    def strfrmt(self, args, each):
        """will format the string with any passed in data"""
        return args.reply(text=args.text.format(*each.data))

    @command
    def echo(self, msg):
        """immediately echoes the arguments"""
        return msg

    @pipeinable_command
    def iterate(self, args, msg):
        """iterate through msg.data and create a new message for each one"""
        for x in msg.data:
            yield msg.reply([x])

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
