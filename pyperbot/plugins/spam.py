from pyperbot.wrappers import plugin, command, outputfilter
from datetime import datetime
from collections import defaultdict
from pyperbot.piping import PipeClosed


@plugin
class Spam:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.spams = defaultdict(lambda: defaultdict(lambda: False))

    @outputfilter
    async def spam(self, initial, inpipe, outpipe):
        time = datetime.now()
        try:
            while 1:
                x = await inpipe.recv()
                if x.command in ["PRIVMSG", "ACTION", "NOTICE"]:
                    if self.spams[x.server][x.params]:
                        if time - self.spams[x.server][x.params] < x(seconds=30):
                            continue
                outpipe.send(x)
        except PipeClosed:
            pass
        finally:
            outpipe.close()
            inpipe.close()

    @command("spam")
    def stopspam(self, message):
        self.spams[message.server][message.params] = datetime.now()
        self.bot.send(message.reply("sorry, I will be quiet for a while"))
