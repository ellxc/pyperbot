from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.shortcuts import create_prompt_application, create_asyncio_eventloop
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit.completion import Completer
from ptpython.completer import PythonCompleter
from aioconsole import aexec
import asyncio
import sys
import traceback
from pyperbot.pyperparser import total
from pyperbot.piping import PipeError
from pyperbot.Message import Message
from itertools import chain

class myCompleter(Completer):
    def __init__(self, bot):
        self.pythoncompleter = PythonCompleter(globals, locals)
        self.bot = bot

    def get_completions(self, document, complete_event):
        if document.text.startswith("#"):
            return WordCompleter(chain(self.bot.commands, self.bot.aliases)).get_completions(document, complete_event)
        else:
            return self.pythoncompleter.get_completions(document, complete_event)


async def interactive_shell(bot):
    eventloop = create_asyncio_eventloop(bot.loop)
    cli = CommandLineInterface(
        application=create_prompt_application(':> ', completer=myCompleter(bot)),
        eventloop=eventloop,

    )

    sys.stdout = cli.stdout_proxy()
    while True:
        try:
            result = await cli.run_async()
            if result.text.startswith("#"):
                parse = total.parseString(result.text[1:], parseAll=True)
                try:
                    resp = await bot.run_parse(parse, Message(server='SHELL'))
                    for res in resp:
                        print(res.text)
                except PipeError as e:
                    for loc, err in sorted(e.exs, key=lambda x: x[0]):
                        if isinstance(err, PipeError):
                            for loc2, err2 in sorted(err.exs, key=lambda x: x[0]):
                                try:
                                    raise err2
                                except Exception:  # how to print to terminal
                                    traceback.print_exc()
                        else:
                            try:
                                raise err
                            except Exception:  # how to print to terminal
                                traceback.print_exc()
            else:
                try:
                    await aexec(result.text, local={'bot': bot})
                except Exception:
                    traceback.print_exc()
        except (EOFError, KeyboardInterrupt):
            bot.loop.stop()
