import datetime

from pyperbot.piping import PipeClosed
from pyperbot.wrappers import plugin, cron, unload, onload, sync, \
    event, trigger, command, complexcommand, pipeinable_command, regex


@plugin
class example:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.count = 0
        if 'count' in config:
            self.count = config['count']

    @onload
    def load(self):
        print("plugin loaded!")

    @unload
    def uload(self):
        print("plugin unloaded!")

    @cron("*/5 * * * *")
    def buzz(self):
        print("buzz", datetime.datetime.now())
        self.count += 1

    @sync
    def sync(self):
        print("plugin synced")

    @event('NOTICE')
    def noticenoticer(self, message):
        print("I saw a notice!")
        self.count += 1

    @trigger(lambda msg: msg.text == 'o.o')
    def face(self, msg):
        self.bot.send(msg.reply('O.O'))
        self.count += 1

    @regex(r'(?P<a>[A-Z])\.(?P=a)')
    def face2(self, msg, match):
        self.bot.send(msg.reply("<{a}.{a}>".format(**match.groupdict()).lower()))

    @command('count')
    def countcommand(self, msg):
        return msg.reply(text=str(self.count))

    @pipeinable_command('face')
    def trailingface(self, initial, msg):
        return msg.reply(msg.text + " 0.0")

    @complexcommand('faces')
    async def beforeandafterface(self, initial, inpipe, outpipe):
        outpipe.send(initial.reply("o.o"))
        try:
            while 1:
                outpipe.send(await inpipe.recv())
        except PipeClosed:
            outpipe.send(initial.reply("o.o"))
        finally:
            inpipe.close()
            outpipe.close()
