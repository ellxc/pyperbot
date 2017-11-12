from concurrent.futures import Future
from multiprocessing import Process
import _thread
import ctypes
from util import async_pipe, PipeClosed
import asyncio
from asyncio.tasks import FIRST_EXCEPTION
from contextlib import contextmanager

@contextmanager
def manage_pipes(*pipes, err=True):
    try:
        yield
    except PipeClosed:
        pass
    except Exception as e:
        if err == True:
            try:
                pipes[-1].send(e)
            except PipeClosed:
                pass
        else:
            pass
    finally:
        for pipe in pipes:
            pipe.close()


class PipeManager:

    def __init__(self, loop=None):
        self._loop = loop or asyncio.get_event_loop()

    @property
    def loop(self):
        return self._loop

    @staticmethod
    def run_future(func, futr, *args, **kwargs):
        print("running", func.__name__, args, kwargs)
        return futr.set_result(func(*args, **kwargs))

    async def schedthreadedfunc(self, func, *args, timeout=None, **kwargs):
        futr = Future()
        t = _thread.start_new_thread(self.run_future, (func, futr) + args, kwargs)
        if timeout is None:
            await asyncio.wrap_future(futr, loop=self.loop)
        else:
            try:
                await asyncio.wait_for(asyncio.wrap_future(futr, loop=self.loop), timeout=timeout, loop=self.loop)
            except asyncio.TimeoutError:
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(t,
                                                                 ctypes.py_object(TimeoutError))
                raise TimeoutError
        return futr.result()

    async def schedproccedfunc(self, func, *args, timeout=None, **kwargs):
        futr = Future()
        p = Process(target=self.run_future, args=((func, futr) + args), kwargs=kwargs)
        p.start()
        if timeout is None:
            await asyncio.wrap_future(futr, loop=self.loop)
        else:
            try:
                await asyncio.wait_for(asyncio.wrap_future(futr, loop=self.loop), timeout=timeout, loop=self.loop)
            except asyncio.TimeoutError:
                p.terminate()
                raise TimeoutError
        return futr.result()

    @staticmethod
    async def _stdout(inpipe, callback, out):
        try:
            while 1:
                x = await inpipe.recv()
                out.append(x)
                print("adding ", x, "to result")
                if callback is not None:
                    callback(x)
        except PipeClosed:
            pass  # print("pipe ended")
        finally:
            inpipe.close()

    def stderr(self, pipe, callback):
        def prnt(x):
            try:
                callback(x.result())
                foo = asyncio.ensure_future(pipe.recv(), loop=self.loop)
                foo.add_done_callback(self.stderr(pipe, callback))
            except PipeClosed:
                try:
                    foo.cancel()
                except:
                    pass
            except asyncio.CancelledError:
                pass
            finally:
                try:
                    foo.cancel()
                except:
                    pass
        return prnt

    async def run_pipe(self, cmds_args, callback=None, collector=lambda x: x, err_callback=print, timeout=15, loop=None):

        # dispatcher = self.schedthreadedfunc  # lambda func, *args, **kwargs: loop.run_in_executor(exe, functools.partial(func, *args, **kwargs), )
        # heavydispatcher = self.schedproccedfunc

        tasks = []
        out = []

        next, first = async_pipe()
        for func, args in cmds_args:
            print(args)
            next3, next2 = async_pipe(loop=loop)
            tasks.append(asyncio.ensure_future(func(args, next, next2),loop=loop if loop is not None else self.loop))
            next = next3

        tasks.append(self._stdout(next, callback, out))
        first.close()

        _= asyncio.gather(*tasks, loop=loop if loop is not None else self.loop, return_exceptions=True)

        try:
            x = await asyncio.wait_for(_, timeout=timeout, loop=loop if loop is not None else self.loop)
            # for t in tasks:
            #     if t.exception() is not None:
            #         raise t.exception()
            return out, x
        except asyncio.TimeoutError:
            _.cancel()
            raise TimeoutError