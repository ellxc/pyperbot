import _thread
import asyncio
import collections
import copy
import ctypes
from asyncio import events, coroutine, locks, sleep
from collections import MutableMapping
from concurrent.futures import Future, ProcessPoolExecutor
from contextlib import contextmanager
from logging import Handler
import async_timeout


class PipeClosed(Exception):
    pass


class PipeEmpty(Exception):
    pass


class ItemAdded(Exception):
    pass


def run_future(func, futr, *args, **kwargs):
    try:
        return futr.set_result(func(*args, **kwargs))
    except Exception as e:
        futr.set_exception(e)


async def schedthreadedfunc(func, *args, timeout=None, **kwargs):
    futr = Future()
    t = _thread.start_new_thread(run_future, (func, futr) + args, kwargs)
    if timeout is None:
        await asyncio.wrap_future(futr)
    else:
        try:
            with async_timeout.timeout(timeout):
                await asyncio.wrap_future(futr)
        except asyncio.TimeoutError:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(t, ctypes.py_object(TimeoutError))
            raise TimeoutError()
    if futr.exception():
        raise futr.exception()
    return futr.result()


x = ProcessPoolExecutor()


async def schedproccedfunc(func, *args, timeout=None, **kwargs):
    f = x.submit(func, *args, **kwargs)
    if timeout is None:
        await asyncio.wrap_future(f)
    else:
        try:
            with async_timeout.timeout(timeout):
                await asyncio.wrap_future(f)
        except asyncio.TimeoutError:
            x.shutdown(wait=False)
            raise TimeoutError()
    return f.result()


class Shielded:
    def __init__(self, pipe):
        self.__dict__ = pipe.__dict__.copy()
        self.close = lambda: None


@coroutine
def wait_for(future, seconds):
    yield from sleep(seconds)
    future.set_result(None)


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
            except Exception:
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


class MutableNameSpace(MutableMapping):
    def __init__(self, data=None, recurse=False):
        if data is None:
            data = {}
        self._data = data
        self._recurse = recurse

    def __repr__(self):
        ret = "{"
        ret += ", ".join(["{}: {}".format(repr(key), repr(val)) for key, val in self._data.items()])
        ret += "}"
        return ret

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __delitem__(self, key):
        del self._data[key]

    def __delattr__(self, item):
        del self._data[item]

    def setdefault(self, key, default=None):
        if key in self._data:
            return self._data[key]
        else:
            self._data[key] = default
            return default

    def copy(self):
        return MutableNameSpace(self._data.copy(), recurse=self._recurse)

    def __getattr__(self, item):
        if item in self._data:
            ret = self._data[item]
            if isinstance(ret, MutableMapping) and not isinstance(ret, MutableNameSpace):
                return MutableNameSpace(ret, recurse=self._recurse)
            else:
                return ret
        else:
            if self._recurse:
                self._data[item] = MutableNameSpace({}, recurse=self._recurse)
                return self._data[item]
            else:
                raise KeyError('%s' % item)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        elif isinstance(value, dict):
            return self._data.__setitem__(key, MutableNameSpace(value, recurse=self._recurse))
        else:
            return self._data.__setitem__(key, value)

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __setitem__(self, key, value):
        return self.__setattr__(key, value)

    def __setstate__(self, vals):
        self._data = vals["data"]
        self._recurse = vals["all"]

    def __getstate__(self):
        return {
            "data": self._data,
            "all": self._recurse,
        }

    def __deepcopy__(self, memodict={}):
        result = self.__class__()
        memodict[id(self)] = result
        result.__init__(copy.deepcopy(self._data, memo=memodict), self._recurse)
        return result


class LocatableException(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex


class MissingArg(Exception):
    def __init__(self, loc, ex):
        self.loc = loc
        self.ex = ex

    def __str__(self):
        return self.ex


class ResultingCallTooLong(Exception):
    pass


class aString(str):

    def quotetype(self, qtype):
        self.qtype = qtype


class bString(aString):
    type = 'r'

    def settype(self, type):
        self.type = type


class NotAuthed(Exception):
    pass


class ExceededRateLimit(Exception):
    pass


class ShitHandler(Handler):
    """
    A handler class which writes logging records, appropriately formatted,
    to a stream. Note that this class does not close the stream, as
    sys.stdout or sys.stderr may be used.
    """

    def __init__(self):
        Handler.__init__(self)

    def flush(self):
        pass

    def emit(self, record):
        print(self.format(record))


@contextmanager
def manage_pipes(*pipes):
    try:
        yield
    except PipeClosed:
        pass
    finally:
        for pipe in pipes:
            pipe.close()
