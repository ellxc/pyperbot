import urllib.parse
import urllib.request

from pyperbot.piping import PipeClosed
from pyperbot.util import schedthreadedfunc
from pyperbot.wrappers import plugin, complexcommand


@plugin
class Sprunge:
    @complexcommand
    async def sprunge(self, initial, inpipe, outpipe):
        spam = []
        try:
            while 1:
                x = await inpipe.recv()
                spam.append(x)
        except PipeClosed:
                data = {'f:1': '\n'.join(m.text for m in spam)}
                response = await schedthreadedfunc(urllib.request.urlopen,
                                                   urllib.request.Request('http://ix.io',
                                                                          urllib.parse.urlencode(data).encode('utf-8')
                                                                          )
                                                   )
                response = response.read().decode()
                outpipe.send(initial.reply(text=response))
        finally:
            outpipe.close()
            inpipe.close()
