import json
import async_timeout
import aiohttp
from pyperbot.wrappers import plugin, command, regex


@plugin
class cleverbot:
    def __init__(self, bot, config):
        self.bot = bot
        self.nick = None
        
    async def chat(self, text):
        async with async_timeout.timeout(30):
            async with aiohttp.ClientSession() as session:
                if self.nick is None:
                    params = params = {"user": "Ih7SiAskrVx87xF1", "key": "oHqp199HRBOBiN5thoXh1naFh6W2Vb07"}
                    async with session.post('https://cleverbot.io/1.0/create', headers={'User-Agent': 'Mozilla/5.0'}, data=params) as resp:
                      response = json.loads(await resp.text())
                      self.nick = response['nick']
            
                params = {"user": "Ih7SiAskrVx87xF1", "key": "oHqp199HRBOBiN5thoXh1naFh6W2Vb07", "text": text, "nick": self.nick}
                async with session.post('https://cleverbot.io/1.0/ask', headers={'User-Agent': 'Mozilla/5.0'}, data=params) as resp:
                    response = json.loads(await resp.text())
                    return response['response']
        
    @command(rate_limit_no=2)
    async def talk(self, message):
        return message.reply(await self.chat(message.text))
    
    @regex("Marvin:(.*)")
    async def direct(self, message, match):
        print("direct message")
        self.bot.send(message.reply(await self.chat(match.groups(1) or "Hello")))
