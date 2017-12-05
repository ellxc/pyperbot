from pyperbot.wrappers import plugin, command
import wikipedia
from wikipedia.exceptions import DisambiguationError
from pyperbot.util import schedthreadedfunc


class Disambiguation(Exception):
    pass


@plugin
class Wiki:

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        if 'lang' in self.config:
            self.lang = self.config.get('lang')
        else:
            self.lang = 'en'

        wikipedia.set_lang(self.lang)

    @command
    @command('w')
    async def wiki(self, message):
        try:
            page = await schedthreadedfunc(wikipedia.page, message.text, timeout=5)
            summary = await schedthreadedfunc(wikipedia.summary, message.text, timeout=5, sentences=3)
        except DisambiguationError as e:
            raise Disambiguation("%s may refer to: %s" % (e.title, "; ".join(e.options[:6])))

        yield message.reply(summary)
        yield message.reply(text="would you like to know more? " + page.url)

    @command
    async def randomwiki(self, message):
        got1 = False
        while not got1:
            try:
                title = await schedthreadedfunc(wikipedia.random, timeout=5)
                page = await schedthreadedfunc(wikipedia.page, title, timeout=5)
                got1 = True
            except DisambiguationError:
                continue
        yield message.reply(text=page.summary)
        yield message.reply(text="would you like to know more? " + page.url)
