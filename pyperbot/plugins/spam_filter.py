import urllib.parse
import urllib.request

from pyperbot.piping import PipeClosed
from pyperbot.util import schedthreadedfunc
from pyperbot.wrappers import plugin, outputfilter


@plugin
class SpamFilter:
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
