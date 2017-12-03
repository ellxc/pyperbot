
import asyncio

from pyperbot.util import async_pipe, PipeClosed


class PipeManager:

    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()

    @property
    def loop(self):
        return self._loop

    @staticmethod
    def run_future(func, futr, *args, **kwargs):
        return futr.set_result(func(*args, **kwargs))

    @staticmethod
    async def _stdout(inpipe, callback, out):
        try:
            while 1:
                x = await inpipe.recv()
                out.append(x)
                if callback is not None:
                    callback(x)
        except PipeClosed:
            pass  # print("pipe ended")
        finally:
            inpipe.close()

    async def run_pipe(self, cmds_args, callback=None, timeout=15, loop=None):
        tasks = []
        out = []

        next_, first = async_pipe()
        for func, args in cmds_args:
            next3, next2 = async_pipe(loop=loop)
            tasks.append(asyncio.ensure_future(func(args, next_, next2), loop=loop if loop is not None else self.loop))
            next_ = next3

        tasks.append(self._stdout(next_, callback, out))
        first.close()

        pipe_sections = asyncio.gather(*tasks, loop=loop if loop is not None else self.loop, return_exceptions=True)

        try:
            x = await asyncio.wait_for(pipe_sections, timeout=timeout, loop=loop if loop is not None else self.loop)
            return out, x
        except asyncio.TimeoutError:
            pipe_sections.cancel()
            raise TimeoutError()


class PipeError(Exception):
    def __init__(self, exs):
        self.exs = exs
