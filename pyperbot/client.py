import asyncio
import logging
from pyperbot.Message import Message
from pyperbot.events import EventManager
import async_timeout

class Recconnect(Exception):
    pass


class IrcClient(asyncio.Protocol):
    transport = None
    closed = False
    ODELIM = b"\r\n"

    def __init__(self, host, port, *, encoding="UTF-8", ssl=True, loop=None, nick="testbot",
                 username=None, password=None, ircname=None, servername=None, reconnect=True):

        self.buffer = b""

        self.host = host
        self.port = port
        self.ssl = ssl
        self.encoding = encoding

        self.nick = nick
        self.user = username or nick
        self.ircname = ircname or nick
        self.password = password
        self.servername = servername or host
        self.reconnect = reconnect
        self.serverconf = {}
        # self.nicks =

        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

        self.em = EventManager(loop=self.loop, name=servername or host or "??? server")

        self.log = logging.getLogger("pyperbot." + servername or host or "??? server", )

        base_events = [
            ("PING", lambda **kwargs: self.send(kwargs['message'].reply(command="PONG", text=kwargs['message'].text))),
            ("433", lambda **kwargs: self.send(
                Message(command='NICK', params=kwargs["message"].params.split()[-1] + "_"))),
            ('005', lambda message: self.serverconf.update(
                {k: v for x in message.params.split() for k, _, v in [x.partition('=')]}))
        ]

        for event, fn in base_events:
            self.em.register_handler(event, fn)

        self.timeout = self.loop.create_future()
        self.loop.create_task(self.timeoutshim())

    async def timeoutshim(self, delay=300):
        while 1:
            try:
                with async_timeout.timeout(delay):
                    await self.timeout
                self.timeout = self.loop.create_future()
            except asyncio.TimeoutError:
                print("no message received in %s seconds, attempting to reconnect" % delay)
                self.closed = True
                while self.closed:
                    try:
                        self.timeout = self.loop.create_future()
                        self.transport.close()
                        await self.loop.create_connection(lambda: self, host=self.host, port=self.port, ssl=self.ssl)
                        self.closed = False
                    except asyncio.TimeoutError:
                        print("failed to reconnect, retrying in 5 seconds")
                        await asyncio.sleep(5)
            except Recconnect:
                print("attempting to reconnect!")
                while self.closed:
                    try:
                        self.timeout = self.loop.create_future()
                        self.transport.close()
                        await self.loop.create_connection(lambda: self, host=self.host, port=self.port, ssl=self.ssl)
                        self.closed = False
                    except asyncio.TimeoutError:
                        print("failed to reconnect, retrying in 5 seconds")
                        await asyncio.sleep(5)
            finally:
                pass

    def data_received(self, data):
        try:
            self.timeout.set_result(1)
        except asyncio.futures.InvalidStateError:
            pass  # self.timeout = self.loop.create_future()
        self.buffer += data
        *lines, self.buffer = self.buffer.split(b"\n")
        for line in lines:
            message = line.decode().strip()
            try:
                m = Message.from_line(message, server=self.servername)
                if m.params == self.nick:
                    m.params = m.nick
                self.log.info("<< %s", m)
                self.em.fire_event(m.command, message=m)
            except Exception as e:
                self.log.debug("Failed to parse line >>> %s \n\t%s", message, repr(e))

    async def on_timeout(self):
        await self.disconnect()
        await self.connect()

    @property
    def loop(self):
        return self._loop

    def send(self, message):
        if self.closed or not self.transport:
            raise RuntimeError("Not connected")
        self.log.info(">> %s", message.to_line())

        self.transport.write(message.to_line().encode() + self.ODELIM)

    async def connect(self, attempts=3):
        if attempts == 0:
            raise Exception("Could not connect")
        if not self.closed:
            await self.disconnect()
        try:
            await self.loop.create_connection(lambda: self, host=self.host, port=self.port, ssl=self.ssl)
        except OSError:
            print("could not connect, retrying in 5")
            await asyncio.sleep(5)
            await self.connect(attempts=attempts-1)

    def connection_made(self, transport):
        self.transport = transport
        self.log.info("connecting to server '%s' %s:%d", self.servername, self.host, self.port)
        self.log.info("sending login info for %s", self.servername)
        if self.password:
            self.transport.write(("PASS " + self.password).encode() + self.ODELIM)
        self.transport.write(('USER ' + self.user + " 0 * :nvPiperbot").encode() + self.ODELIM)
        self.transport.write(('NICK ' + self.nick).encode() + self.ODELIM)

    def connection_lost(self, exc):
        if not self.closed:
            self.closed = True
            self.transport.close()

        if self.reconnect:
            self.timeout.set_exception(Recconnect())
        else:
            self.timeout.cancel()

    async def disconnect(self):
        if not self.closed and self.transport:
            try:
                self.transport.close()
            finally:
                self.closed = True
