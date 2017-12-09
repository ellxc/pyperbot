import async_timeout
import aiohttp
from pyperbot.piping import PipeClosed
from pyperbot.wrappers import plugin, complexcommand, outputfilter


@plugin
class Sprunge:

    @complexcommand
    async def sprunge(self, initial, inpipe,  outpipe):
        dat = []
        try:
            while 1:
                x = await inpipe.recv()
                dat.append(x)
        except PipeClosed:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    data = {'f:1': '\n'.join(m.text for m in dat)}
                    async with session.post('http://ix.io', data=data) as resp:
                        response = await resp.text()
            outpipe.send(initial.reply(text=response))
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
                async with async_timeout.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        data = {'f:1': '\n'.join(m.text for m in spam)}
                        async with session.post('http://ix.io', data=data) as resp:
                            response = await resp.text()
                outpipe.send(initial.reply(text="spam detected! here is the output: %s" % response))
            elif len(spam) == 4:
                outpipe.send(spam[-1])
        finally:
            outpipe.close()
            inpipe.close()
