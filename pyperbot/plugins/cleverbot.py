import json
import async_timeout
import aiohttp
from pyperbot.wrappers import plugin, command


@plugin
class cleverbot:
    def __init__(self, bot, config):
        self.nick = None
        
    @command(rate_limit_no=2)
    async def talk(self, message):
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                if self.nick is None:
                    params = params = {"user": "Ih7SiAskrVx87xF1", "key": "oHqp199HRBOBiN5thoXh1naFh6W2Vb07"}
                    async with session.post('https://cleverbot.io/1.0/create', headers={'User-Agent': 'Mozilla/5.0'}, data=params) as resp:
                      response = json.loads(await resp.text())
                      self.nick = response['nick']
            
                params = {"user": "Ih7SiAskrVx87xF1", "key": "oHqp199HRBOBiN5thoXh1naFh6W2Vb07", "text": message.text, "nick": self.nick}
                async with session.post('https://cleverbot.io/1.0/ask', headers={'User-Agent': 'Mozilla/5.0'}, data=params) as resp:
                    response = json.loads(await resp.text())
                    return message.reply(response['response'])
