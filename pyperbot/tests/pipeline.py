import asyncio
import unittest

import Message

from pyperbot import Pyperbot
from pyperbot.pyperparser import total


class pipelinetests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.bot = Pyperbot(self.loop)
        self.bot.load_plugin_file("core")

    def test_pipeline(self):
        x = self.loop.run_until_complete(self.bot.run_parse(total.parseString("echo foo"), Message.Message()))
        assert (x[0].text == 'foo')
