import asyncio
from collections import defaultdict
from itertools import combinations


def event_split(y):
    a, *t = y.split(".")[::-1]
    for x in range(len(t)):
        for z in combinations(t, x):
            yield ".".join((*z, a))
    yield y


class EventManager:
    def __init__(self, loop=None, parent=None, name=None):
        if not loop:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self.events = defaultdict(lambda: asyncio.Future(loop=self.loop))
        self.handlers = defaultdict(list)
        self.parent = parent
        self.name = name

    @property
    def loop(self):
        return self._loop

    def add_handler(self, event, fn):
        self.events[event].add_done_callback(lambda res: fn(**res.result()))

    def fire_event(self, event, **kwargs):
        for ev in event_split(event):
            if ev in self.events:
                self.events[ev].set_result(kwargs)
                del self.events[ev]
                for fn in self.handlers[ev]:
                    self.add_handler(ev, fn)
        if self.parent:
            self.parent.fire_event((self.name or "???")+"."+event, **kwargs)

    def register_handler(self, event, fn):
        if fn in self.handlers[event]:
            raise ValueError("event handler exists")
        self.handlers[event].append(fn)
        self.add_handler(event, fn)

    def deregister_handler(self, event, fn):
        self.handlers[event].remove(fn)
        del self.events[event]
        if self.handlers[event]:
            for fn in self.handlers[event]:
                self.add_handler(event, fn)
