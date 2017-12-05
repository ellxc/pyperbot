import re
from pyperbot.wrappers import plugin, regex
import aiohttp
from bs4 import BeautifulSoup
import async_timeout
from asyncio import as_completed
from collections import OrderedDict

units = [
    (1024 ** 5, 'P'),
    (1024 ** 4, 'T'),
    (1024 ** 3, 'G'),
    (1024 ** 2, 'M'),
    (1024 ** 1, 'K'),
    (1024 ** 0, 'B'),
]


def size(bites):
    for factor, suffix in units:
        if bites >= factor:
            break
    amount = bites / factor
    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return format(amount, ".2f") + suffix


@plugin
class TitleReader:
    linkregex = re.compile(r"(?:http[s]?://|www)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    async def getresp(self, session, link, index, multi=False):
        async with session.get(link) as resp:
            content = resp.headers.get('Content-Type', 'Unknown')
            length = resp.headers.get('Content-Length', '0')
            try:
                length = size(int(length))
            except:
                length = "0B"

            if 'text/html' in content:
                text = await resp.text()

                soup = BeautifulSoup(text, 'html.parser')
                title = soup.title.string
                if multi:
                    return "[%d] Title: " % index + title
                else:
                    return "Title: " + title
            else:
                if multi:
                    return "[%d] [%s;%s]" % (index, content, length)
                else:
                    return "[%s; %s]" % (content, length)

    @regex('^.*(?:https?://www|https?://|www).*$')
    async def url(self, msg, match):
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                links = OrderedDict()
                links.update(((link, None) if link.startswith("http") else ("http://"+link, None) for link in
                              self.linkregex.findall(msg.text)))
                for f in as_completed(map(lambda il: self.getresp(session, il[1], il[0]+1, multi=len(links) > 1),
                                          enumerate(links))):
                    self.bot.send(msg.reply(text=await f))
