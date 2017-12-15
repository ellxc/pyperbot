import copy
import datetime
import re

SPLIT_REGEX = r"^(?::(?:(?:(?P<nick>\S+)!)?(?:(?P<user>\S+)@)?(?P<domain>\S+) +))?" \
              r"(?P<command>\S+)(?: +(?!:)(?P<params>.+?))?(?: *:(?:\x01(?P<ctcp>\w+) )?(?P<text>.+?))?\x01?$"


class Message:
    def __init__(self, server=None, nick="", user="", domain="", command="", params="", ctcp="",
                 timestamp=None, text=None, data=None, str_fn=None):
        self.server = server
        self.nick = nick
        self.user = user
        self.domain = domain
        self._command = command
        self.params = params
        self.ctcp = ctcp
        self._text = None
        self.timestamp = timestamp or datetime.datetime.now()

        self.data = data
        self.text = text
        self.str_fn = str_fn if str_fn is not None else lambda x: x if isinstance(x, str) else" ".join(map(str, x))

    @property
    def text(self):
        if self._text is None:
            if self.data is not None:
                return self.str_fn(self.data)
            return ""
        return self._text

    @text.setter
    def text(self, val):
        if val:
            if val.startswith("\001"):
                cmd, *val = val.split(" ")
                val = " ".join(val)
                self.ctcp = cmd[1:]
                if val.endswith("\001"):
                    val = val[:-1]
        self._text = val

    @property
    def command(self):
        return "CTCP:"+self.ctcp if self.ctcp else self._command

    @command.setter
    def command(self, val):
        self._command = val

    def to_line(self):
        text = self.text.replace("\r", "").replace("\n", "")
        return "%s %s%s" % (
            self.command,
            self.params,
            " :%s%s%s" % (("\001%s " % self.ctcp if self.ctcp else ""),
                          bytes(text, "utf-8")[:550].decode(),
                          ("\001" if self.ctcp else "")) if self.text else "",
            )

    def to_pretty(self):
        text = self.timestamp.strftime("%x %X")
        text += " "
        if self.ctcp:
            text += " * %s " % self.nick
        else:
            text += "< %s> " % self.nick
        text += self.text.rstrip("\n")
        return text

    def reply(self, data=None, text=None, ctcp=None, command=None, params=None, str_fn=None):
        return Message(server=self.server, nick=self.nick, command=self.command if command is None else command,
                       domain=self.domain, ctcp=self.ctcp if ctcp is None else ctcp, user=self.user,
                       params=self.params if params is None else params, text=text, data=data, str_fn=str_fn)

    def copy(self):
        return copy.copy(self)

    def __lt__(self, other):
        return (self.command.lower() == "ping" and not other.command.lower() == "ping") \
               or self.timestamp < other.timestamp

    def __str__(self):
        return "{}: {} {} {}:{}".format(
                self.server,
                (" <" + self.nick + "(" + self.user + ("@" if self.user else "") + self.domain + ")" + ">")
                if self.domain else "",
                "CTCP:"+self.ctcp if self.ctcp else self.command,
                self.params,
                bytes(self.text, "utf-8")[:550].decode(),
            )

    @staticmethod
    def from_line(line, server):
        if not line:
            return
        else:
            return Message(server, **re.match(SPLIT_REGEX, line).groupdict(""))
