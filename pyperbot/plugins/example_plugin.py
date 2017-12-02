import datetime

from pyperbot.wrappers import plugin, cron, unload, onload


@plugin
class example:
    @onload
    def load(self):
        print("plugin loaded!!!1!!one!!")

    @unload
    def uload(self):
        print("plugin unloaded!!1one11!!")

    @cron("*/2 * * * *")
    def fizz(self):
        print("fizz", datetime.datetime.now())

    @cron("*/3 * * * *")
    def buzz(self):
        print("buzz", datetime.datetime.now())
