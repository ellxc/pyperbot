import _thread
import asyncio
import collections
import ctypes
from asyncio import events, coroutine, locks, sleep
from concurrent.futures import Future, ProcessPoolExecutor


class PipeClosed(Exception):
    pass


class PipeEmpty(Exception):
    pass


class ItemAdded(Exception):
    pass


def run_future(func, futr, *args, **kwargs):
    return futr.set_result(func(*args, **kwargs))


async def schedthreadedfunc(func, *args, timeout=None, **kwargs):
    futr = Future()
    t = _thread.start_new_thread(run_future, (func, futr) + args, kwargs)
    if timeout is None:
        await asyncio.wrap_future(futr)
    else:
        try:
            await asyncio.wait_for(asyncio.wrap_future(futr), timeout=timeout)
        except asyncio.TimeoutError:
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(t,
                                                             ctypes.py_object(TimeoutError))
            raise TimeoutError()
    return futr.result()


x = ProcessPoolExecutor()


async def schedproccedfunc(func, *args, timeout=None, **kwargs):
    f = x.submit(func, *args, **kwargs)
    if timeout is None:
        await asyncio.wrap_future(f)
    else:
        try:
            await asyncio.wait_for(asyncio.wrap_future(f), timeout=timeout)
        except asyncio.TimeoutError:
            x.shutdown(wait=False)
            raise TimeoutError()
    return f.result()



class shielded():
    def __init__(self, pipe):
        self.__dict__ = pipe.__dict__.copy()
        self.close = lambda: None

@coroutine
def wait_for(future, seconds):
    yield from sleep(seconds)
    future.set_result(None)


async def aliashelper(args, inpipe, outpipe):
    called = False
    try:
        while 1:
            x = await inpipe.recv()
            called = True
            if args.args:
                outpipe.send(x.reply(text=args.text.format(x.data), data=[args.data, x.data]))
            else:
                outpipe.send(x)
    except PipeClosed:
        if not called:
            outpipe.send(args)
    finally:
        outpipe.close()
        inpipe.close()


class WaitableQueue:
    def __init__(self, *, loop=None):

        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop

        self._closed = False
        self._getters = collections.deque()
        self._pollers = collections.deque()
        self._unfinished_tasks = 0
        self._finished = locks.Event(loop=self._loop)
        self._finished.set()
        self._queue = collections.deque()

    def close(self):
        self._closed = True
        for getter in self._getters:
            if not getter.done():
                getter.set_exception(PipeClosed())

    def _get(self):
        return self._queue.popleft()

    def _put(self, item):
        self._queue.append(item)

    def _wakeup_next(self, waiters):
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break

    def __repr__(self):
        return '<{} at {:#x} {}>'.format(
            type(self).__name__, id(self), self._format())

    def __str__(self):
        return '<{} {}>'.format(type(self).__name__, self._format())

    def _format(self):
        result = ''
        if getattr(self, '_queue', None):
            result += ' _queue={!r}'.format(list(self._queue))
        if self._getters:
            result += ' _getters[{}]'.format(len(self._getters))
        if self._unfinished_tasks:
            result += ' tasks={}'.format(self._unfinished_tasks)
        return result

    def qsize(self):
        return len(self._queue)

    def empty(self):
        return not self._queue

    def send(self, item):
        if self._closed:
            raise PipeClosed()
        self._put(item)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)
        self._wakeup_next(self._pollers)

    @coroutine
    def poll(self, timeout=0):
        if timeout == 0:
            return self.empty()
        if self._closed:
            raise PipeClosed()
        poller = self._loop.create_future()
        self._pollers.append(poller)
        self._loop.ensure_future(wait_for(poller, timeout))
        try:
            yield from poller
        except ItemAdded:
            return True

    @coroutine
    def recv(self):
        while self.empty():
            if self._closed:
                raise PipeClosed()
            getter = self._loop.create_future()
            self._getters.append(getter)
            try:
                yield from getter
            except PipeClosed:
                raise
            except:
                getter.cancel()
                if not self.empty() and not getter.cancelled():
                    self._wakeup_next(self._getters)
                raise
        return self.recv_nowait()

    def recv_nowait(self):
        if self.empty():
            raise PipeEmpty
        item = self._get()
        return item

    def task_done(self):
        if self._unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self._unfinished_tasks -= 1
        if self._unfinished_tasks == 0:
            self._finished.set()

    @coroutine
    def join(self):
        if self._unfinished_tasks > 0:
            yield from self._finished.wait()


class RightShim:
    def __init__(self, q):
        self.send = q.send
        self.join = q.join
        self.empty = q.empty
        self.qsize = q.qsize
        self.close = q.close


class LeftShim:
    def __init__(self, q):
        self.recv = q.recv
        self.recv_nowait = q.recv_nowait
        self.poll = q.poll
        self.empty = q.empty
        self.qsize = q.qsize
        self.close = q.close


def async_pipe(loop=None):
    a = WaitableQueue(loop=loop)
    return LeftShim(a), RightShim(a)
