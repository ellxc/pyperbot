from pyperbot.wrappers import plugin, complexcommand, regex
from pyperbot.piping import PipeClosed
from pyperbot.util import schedthreadedfunc
import re


@plugin
class Sed:
    sed_pattern = re.compile(r"^ *s([:/%|!@,])((?:(?!\1)[^\\]|\\.)*)\1((?:(?!\1)[^\\]|\\.)*)\1([gi\d]*)(?: +(.+))?")
    grep_pattern = re.compile(r" */(.+)/([i]*)|(.+)")

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @regex(r"^ *s([:/%|!@,])((?:(?!\1)[^\\]|\\.)*)\1((?:(?!\1)[^\\]|\\.)*)\1([gi\d]*)(?: +(.+))?")
    async def sedregex(self, msg, match):
        delim, find, sub, flags, _ = match.groups()
        sub = re.sub(r"\\" + delim, delim, sub)
        action = False

        text = ''
        for msg in reversed(list(self.bot.message_buffer[msg.server][msg.params])):
            matchobj = await schedthreadedfunc(re.search, find, msg.text,
                                               **({"flags": re.IGNORECASE} if "i" in flags else {}))
            if matchobj:
                text = msg.text
                if msg.ctcp == "ACTION":
                    action = True
                break
        if not text:
            self.bot.send(msg.reply("no matching message found"))
            return

        if not sub:
            sub = ""

        text = await schedthreadedfunc(self.sub, delim, find, sub, flags, text, timeout=2)
        result = msg.reply(text)

        if action:
            result.ctcp = "ACTION"
        self.bot.send(result)

    @complexcommand
    async def sed(self, inital, inpipe, outpipe):
        """sed s/find/replace/flags [text] -> accepts piped in text if no text was specified"""
        try:
            match = self.sed_pattern.search(inital.text)
            if not match:

                raise Exception("invalid pattern")

            delim, find, sub, flags, text = match.groups()

            if text:
                text = self.sub(delim, find, sub, flags, text)
                outpipe.send(inital.reply(text))
            else:
                while 1:
                    x = await inpipe.recv()
                    text = await schedthreadedfunc(self.sub, delim, find, sub, flags, x.text, timeout=2)
                    outpipe.send(x.reply(text))
        except PipeClosed:
            pass
        finally:
            inpipe.close()
            outpipe.close()

    @staticmethod
    def sub(delim, find, sub, flags, text):
        sub = re.sub(r"\\" + delim, delim, sub)
        kwargs = {"count": 1}
        if "i" in flags:
            kwargs["flags"] = re.IGNORECASE
        if not sub:
            sub = ""
        index = re.search(r".*?(\d+)", flags)
        if "g" not in flags and index is not None:
            index = int(index.group(1))
            matchobj = [x for x, y in zip(
                re.finditer(find, text, **({"flags": re.IGNORECASE} if "i" in flags else {})),
                range(index))
                ][-1]
            text = text[:matchobj.start()] + matchobj.expand(sub) + text[matchobj.end():]
            result = text
        else:
            if "g" in flags:
                kwargs["count"] = 0
            result = re.sub(find, sub, text, **kwargs)

        return result
