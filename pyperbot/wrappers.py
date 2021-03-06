import functools
import inspect

import crontab

from pyperbot.util import PipeClosed, NotAuthed, ExceededRateLimit
from collections import deque

def plugin(_class):
    _class._plugin = True
    _class._name = _class.__name__
    if _class.__init__ == object.__init__:
        _class.__init__ = lambda self, bot, config: setattr(self, "bot", bot)
    return _class


def onload(func):
    func._onload = True
    return func


def unload(func):
    func._unload = True
    return func


def sync(func):
    func._sync = True
    return func


def env(name):
    def wrapper(func):
        if hasattr(func, '_envs'):
            func._envs.append(name)
            return func
        func._envs = [name]
        return func

    if type(name) is not str:
        raise Exception("invalid env name")
    return wrapper

def cron(cr=None):
    def wrapper(func):
        if hasattr(func, '_crons'):
            func._crons.append(crontab.CronTab(cr))
            return func
        func._crons = [crontab.CronTab(cr)]
        return func
    if type(cr) is not str:
        raise Exception("incorrect or no cron specified")
    return wrapper


def event(ev=None):
    def wrapper(func):
        if hasattr(func, '_events'):
            func._events.append(ev)
            return func
        func._events = [ev]
        return func
    if type(ev) is not str:
        raise Exception("incorrect or no event specified")
    return wrapper


def trigger(trigger_=None):
    def wrapper(func):
        if hasattr(func, '_triggers'):
            func._triggers.append(trigger_)
            return func
        func._triggers = [trigger_]
        return func
    if trigger is None:
        raise Exception("no trigger specified")
    else:
        return wrapper


def regex(reg,flags=0):
    def wrapper(func):
        if hasattr(func, '_regexes'):
            func._regexes.append(reg)
            return func
        func._regexes = [reg]
        return func

    if type(reg) is not str:
        raise Exception("incorrect or no regex specified")
    return wrapper


def inputfilter(func):
    func._inputfilter = True
    return func


def outputfilter(priority=None):
    def wrapper(_func):
        if inspect.isfunction(priority):
            pr = 0
        else:
            pr = priority
        _func._outputfilter = pr
        return _func

    if inspect.isfunction(priority):
        return wrapper(priority)
    else:
        return wrapper


def classcommand(word = None):
    def wrapper(clas):

        if inspect.isclass(word):
            name = word.__name__
        else:
            name = word

        if hasattr(clas, '_commands'):
            clas._commands.append(name)
            return clas
        clas._commands = [name]

        if not hasattr(clas, "__exit__"):
            clas.__exit__ = lambda x,  *args: None


        if not hasattr(clas, "__enter__"):
            clas.__enter__ = lambda x, *args: x

        if not hasattr(clas, "__init__"):
            clas.__init__ = lambda args, inpipe, outpipe: None

        if not hasattr(clas, "__call__"):
            clas.__call__ = lambda args, remain, x: None

        # sig = inspect.signature(clas)
        #
        #
        # if len(sig.parameters) == 1:
        #     __func = lambda _args, _remain, _x: caller(_x)
        # elif len(sig.parameters) > 1:
        #
        #     temp = list(sig.parameters.values())[0].annotation
        #     if isinstance(temp, tuple):
        #         expected_args, expected_longargs = temp
        #         args, remain = getopt.gnu_getopt(shlex.split(args), expected_args, expected_longargs)
        #     elif isinstance(temp, str):
        #         expected_args = temp
        #         args, remain = getopt.gnu_getopt(shlex.split(args), expected_args, [])
        #
        # if len(sig.parameters) == 3:
        #     pass
        # elif len(sig.parameters) == 2:
        #     __func = lambda _args, _remain, _x: caller((_args, _remain), _x)
        # else:
        #     raise Exception("unrecognised number of call args")


        @functools.wraps(clas)
        async def inner(this, args, inpipe, outpipe):
            ranonce = False
            try:

                # temp = list(inspect.signature(clas).parameters.values())[0].annotation
                # if isinstance(temp, tuple):
                #     expected_args, expected_longargs = temp
                #     args = getopt.gnu_getopt(shlex.split(args), expected_args, expected_longargs)
                # elif isinstance(temp, str):
                #     expected_args = temp
                #     args = getopt.gnu_getopt(shlex.split(args), expected_args, [])


                with clas(args, inpipe, outpipe) as caller:

                    # sig = inspect.signature(caller)
                    # inexpect = list(sig.parameters.values())[-1].annotation
                    # outexpect = sig.return_annotation


                    def outfunc(x, out):
                        y = caller(x)
                        # if outexpect != inspect._empty and not isinstance(y, outexpect):
                        #     raise ValueError("unexpected output, expected " + str(outexpect) + " got " + str(type(y)))
                        if y is not None:
                            out.send(y)

                    while 1:
                        x = await inpipe.recv()
                        # if inexpect != inspect._empty and  not isinstance(x, inexpect):
                        #     raise ValueError("unexpected input, expected " + str(inexpect) + " got " + str(type(x)))
                     #   print("received", x, "performing func", caller.__class__.__name__)
                        outfunc(x, outpipe)
            except PipeClosed:
                pass  # pipe ended
            except Exception as e:
                raise e
            finally:
                outpipe.close()
                inpipe.close()

        return inner
    if inspect.isclass(word):
        return wrapper(word)
    else:
        return wrapper

def complexcommand(word=None):
    def wrapper(_func):
        if inspect.isfunction(word):
            name = word.__name__
        else:
            name = word
        if hasattr(_func, '_commands'):
            _func._commands.append(name)
        else:
            _func._commands = [name]
        return _func
    if inspect.isfunction(word):
        return wrapper(word)
    else:
        return wrapper


def wrapinner(func, admin=False, rate_limit_no=0, rate_limit_period=10):
    sig = inspect.signature(func)
    # params = len(sig.parameters)
    #
    # print(sig.parameters)
    #
    # if len(sig.parameters) == 3:


    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def outfunc(this, *_, out):
            y = await func(this, *_)
            if y is not None:
                out.send(y)
    elif inspect.isasyncgenfunction(func):
        @functools.wraps(func)
        async def outfunc(this, *_, out):
            async for z in func(this, *_):
                out.send(z)
    elif inspect.isgeneratorfunction(func):
        @functools.wraps(func)
        async def outfunc(this, *_, out):
            y = func(this, *_)
            for z in y:
                out.send(z)
    else:
        @functools.wraps(func)
        async def outfunc(this, *_, out):
            y = func(this, *_)
            if y is not None:
                out.send(y)

    if rate_limit_no:
        limiter = deque(maxlen=rate_limit_no)
        @functools.wraps(func)
        async def ratelimted(this, *args, out):
            if len(limiter) == rate_limit_no and (args[0].timestamp - limiter[0]).total_seconds() < rate_limit_period:
                raise ExceededRateLimit("command '%s' is rate limited to %d calls every %d seconds" %
                                        (func.__name__, rate_limit_no, rate_limit_period))
            limiter.append(args[0].timestamp)
            return await outfunc(this, *args, out=out)
    else:
        ratelimted = outfunc

    if admin:
        @functools.wraps(func)
        async def final(this, *args, out):
            if await this.bot.is_authed(args[0]):
                return await ratelimted(this, *args, out=out)
            else:
                raise NotAuthed("you are not an admin!")

    else:
        final = ratelimted

    return final


def command(word=None, admin=False, rate_limit_no=0, rate_limit_period=10):  # multilevel wrapper drifting

    def wrapper(_func):

        if inspect.isfunction(word):
            name = word.__name__
        elif word is None:
            name = _func.__name__
        else:
            name = word

        if hasattr(_func, '_commands'):
            _func._commands.append(name)
            return _func
        _func._commands = [name]

        if admin:
            _func._admin = True

        outfunc = wrapinner(_func, admin=admin, rate_limit_no=rate_limit_no, rate_limit_period=rate_limit_period)

        @functools.wraps(_func)
        async def inner(this, args, inpipe, outpipe):
            try:
                await outfunc(this, args, out=outpipe)
            except PipeClosed:
                pass  # pipe ended
            except Exception as e:
                raise e
            finally:
                outpipe.close()
                inpipe.close()

        return inner
    if inspect.isfunction(word):
        return wrapper(word)
    else:
        return wrapper


def pipeinable_command(word=None, admin=False, rate_limit_no=0, rate_limit_period=10):

    def wrapper(_func):
        if inspect.isfunction(word):
            name = word.__name__
        else:
            name = word

        if hasattr(_func, '_commands'):
            _func._commands.append(name)
            return _func
        _func._commands = [name]

        if admin:
            _func._admin = True

        outfunc = wrapinner(_func)

        if rate_limit_no:
            limiter = deque(maxlen=rate_limit_no)

        @functools.wraps(_func)
        async def inner(this, args, inpipe, outpipe):
            if admin:
                if not await this.bot.is_authed(args[0]):
                    raise NotAuthed("you are not an admin!")

            try:
                while 1:
                    x = await inpipe.recv()
                    if rate_limit_no:
                        if len(limiter) == rate_limit_no and \
                                        (x.timestamp - limiter[0]).total_seconds() < rate_limit_period:
                            raise ExceededRateLimit("command '%s' is rate limited to %d calls every %d seconds" %
                                                    (_func.__name__, rate_limit_no, rate_limit_period))
                        limiter.append(x.timestamp)
                    await outfunc(this, args, x, out=outpipe)
            except PipeClosed:
                pass  # pipe ended
            except Exception as e:
                raise e
            finally:
                outpipe.close()
                inpipe.close()


        return inner
    if inspect.isfunction(word):
        return wrapper(word)
    else:
        return wrapper

# found a cron parser, so this is incomplete
# class run:
#     def __init__(self, *args):
#         if args:
#             print("straight away")
#
#     def __call__(self, func):
#         func._scheds = []
#
#         return func
#
#     def at(self, time_):
#         if type(time_) is str:
#             time_ = parser.parse(time_).time()
#         elif type(time_) is datetime:
#             time_ = time_.time()
#         if type(time_) is time:
#             self._at = time_
#             return self
#         raise Exception("not a valid time")
#
#     def on(self, date_):
#         if type(date_) is str:
#             date_ = parser.parse(date_).date()
#         elif type(date_) is datetime:
#             date_ = date_.date()
#         if type(date_) is date:
#             self._on = date_
#             return self
#         raise Exception("not a valid date")
#
#     def every(self, delta):
#         return self
#
#     def startat(self, time):
#         return self
#
#     def starton(self, date):
#         return self
#
#     def count(self, no):
#         return self