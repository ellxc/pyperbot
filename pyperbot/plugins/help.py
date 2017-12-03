from inspect import getdoc

from pyperbot.piping import PipeClosed
from pyperbot.wrappers import plugin, command, complexcommand


@plugin
class Help:
    @command
    def plugins(self, message):
        """list the loaded plugins"""
        return message.reply(list(self.bot.plugins.keys()), "loaded plugins: " + ", ".join(self.bot.plugins.keys()))

    @command
    def commands(self, message):
        """list the available commands"""
        return message.reply(list(self.bot.commands.keys()),
                             "available commands: " + ", ".join(self.bot.commands.keys()))

    @command
    def aliases(self, message):
        """list aliases"""
        return message.reply(list(self.bot.aliases.keys()), "saved aliases: " + ", ".join(self.bot.aliases.keys()))

    @command
    def expand(self, message):
        """shows an aliases true form"""
        if message.data:
            a = message.data[0]
            if a in self.bot.aliases:
                s = "#alias %s = %s" % (a, self.bot.aliases[a])
                return message.reply(text=s)
            else:
                return message.reply(text="alias %s not found" % a)
        else:
            return message.reply(text="please specify an alias")

    @complexcommand
    async def help(self, args, inpipe, outpipe):
        """you meta"""
        called = False
        try:
            while 1:
                x = await inpipe.recv()
                called = True
                doc = getdoc(x.data)
                if not doc:
                    outpipe.send(args.reply("No help found for passed object '%s'" % x.data.__class__.__name__))
                else:
                    firstline = "%s: %s" % (x.data.__class__.__name__, doc.split("\n")[0])
                    outpipe.send(args.reply(doc, firstline))
        except PipeClosed:
            if not called:
                if args.data:
                    try:
                        com = args.data[0]
                        func = self.bot.commands[com]
                    except KeyError:
                        raise Exception("specifed command not found")
                    doc = func.__doc__
                    if not doc:
                        outpipe.send(args.reply("No help found for specified command"))
                    else:
                        firstline = "%s: %s" % (com, doc.split("\n")[0])
                        outpipe.send(args.reply(doc, firstline))
                else:
                    outpipe.send(args.reply(text="Use this command by passing in objects or specifying commands"))
                    outpipe.send(args.reply(text="A list of commands can be found with #commands, aliases at #aliases"))
                    outpipe.send(args.reply(text="more help is available online at https://github.com/ellxc/pyperbot"))
        finally:
            outpipe.close()
            inpipe.close()
