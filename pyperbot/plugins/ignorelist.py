from pyperbot.wrappers import plugin, inputfilter


@plugin
class Ignore:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @inputfilter
    def ignorelist(self, msg):
        if msg.nick in self.config.get(msg.server, {}):
            return False
        return True
