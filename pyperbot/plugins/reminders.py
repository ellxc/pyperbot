import datetime

from dateutil import parser

from pyperbot.wrappers import plugin, command

units = {
    "year"        : 31536000,
    "years"       : 31536000,
    "fortnight"   : 1209600,
    "fortnights"  : 1209600,
    "week"        : 604800,
    "weeks"       : 604800,
    "day"         : 86400,
    "days"        : 86400,
    "hour"        : 3600,
    "hours"       : 3600,
    "min"         : 60,
    "mins"        : 60,
    "minute"      : 60,
    "minutes"     : 60,
    "second"      : 1,
    "seconds"     : 1,
    "sec"         : 1,
    "secs"        : 1,
    "moment"      : 90,
    "moments"     : 90,
    "milliseconds": 0.0001,
    "millisecond" : 0.0001,
    "ms"          : 0.0001,
}

quants = {
    "a"        : 1,
    "an"       : 1,
    "one"      : 1,
    "two"      : 2,
    "couple"   : 2,
    "three"    : 3,
    "few"      : 3,
    "four"     : 4,
    "five"     : 5,
    "six"      : 6,
    "seven"    : 7,
    "eight"    : 8,
    "nine"     : 9,
    "ten"      : 10,
    "eleven"   : 11,
    "twelve"   : 12,
    "dozen"    : 12,
    "thirteen" : 13,
    "fourteen" : 14,
    "fifteen"  : 15,
    "sixteen"  : 16,
    "seventeen": 17,
    "eighteen" : 18,
    "nineteen" : 19,
    "twenty"   : 20,
    "thirty"   : 30,
    "forty"    : 40,
    "fifty"    : 50,
    "sixty"    : 60,
    "seventy"  : 70,
    "eighty"   : 80,
    "ninety"   : 90,
    "hundred"  : 100,
    "thousand" : 1000,
    "million"  : 1000000,
    "billion"  : 1000000000,
    "trillion" : 1000000000000,
}


@plugin
class reminders:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.reminders = []

    @command
    def remind(self, message):
        if message.data[1:2] == ["in"]:
            try:
                target, _, quant, unit, *msg = message.data
            except:
                raise Exception("invalid syntax")

            if quant in quants:
                quant = quants[quant]
            else:
                try:
                    quant = float(quant)
                except:
                    Exception("unknown quantity: %s" % quant)

            if unit in units:
                unit = units[unit]
            else:
                raise Exception("unkown unit: %s" % unit)
            if msg[0:1] == ["to"]:
                msg = msg[1:]
            msg = " ".join(msg)

            total = quant * unit

            settime = datetime.datetime.now() + datetime.timedelta(seconds=total)

            if target == "me":
                target = message.nick

            settext = msg or "reminder!"
            responsetext = "reminder set to go in %s!" % str(datetime.timedelta(seconds=total))
        elif message.text.split()[1:2] == ["at"] or message.text.split()[1:2] == ["on"]:
            target, _, *rest = message.data
            if 'to' in rest:
                x = rest.index('to')
                date = rest[:x]
                msg = " ".join(rest[x:])
            else:
                date = " ".join(rest)
                msg = ''
            settime = parser.parse(date, fuzzy=True)
            if target == "me":
                target = message.nick
            responsetext = "reminder set for %s!" % str(settime)
            settext = msg or "reminder!"
        else:
            raise Exception("invalid format you pleb")

        y = message.reply(text=target + ": " + settext)

        self.reminders.append((y, settime))
        self.bot.loop.call_later((settime - datetime.datetime.now()).total_seconds(),
                                 self.remindshim(y, (y, settime)), )

    def remindshim(self, message, reminder):
        def foo():
            self.bot.send(message)
            self.reminders.remove(reminder)

        return foo
