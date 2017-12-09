import re
import shelve
from collections import defaultdict
from pyperbot.wrappers import plugin, command, env, regex, onload, unload, sync, cron


@plugin
class Karma:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.store = {}
        if 'filename' in self.config:
            self.filename = self.config['filename']
        else:
            self.filename = "./karma.shelf"

    @onload
    def onload(self):
        self.store = shelve.open(self.filename)

    @cron("*/10 * * * *")
    @sync
    def save(self):
        self.store.sync()

    @unload
    def unload(self):
        self.store.close()

    @command
    def karma(self, msg):
        """returns how much karma you have gotten or a dict of the specified names"""
        if not msg.data:
            d = self.store.get(msg.nick, 0)
            l = lambda data: "%s: your karma is %d" % (msg.nick, data)
        else:
            d = {nick: self.store.get(nick, 0) for nick in msg.data}
            l = lambda data: "karma: " + ", ".join("%s: %d" % (nick, karma) for nick, karma in data.items())
        return msg.reply(data=d, str_fn=l)

    @env('karma')
    def env(self):
        return defaultdict(lambda: 0, **{n: k for n, k in self.store.items()})

    @regex(r"\S+(?:\+\+|--)")
    def regex(self, msg, match):
        for instance in re.finditer(r"(\S+)(\+\+|--)", msg.text):
            target = instance.group(1)
            mod = {"++": 1, "--": -1}[instance.group(2)]
            if target not in self.store:
                self.store[target] = 0
            self.store[target] += mod
