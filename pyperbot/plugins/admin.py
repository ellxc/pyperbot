from pyperbot.wrappers import plugin, command


@plugin
class Admin:
    @command(admin=True)
    def pluginload(self, msg):
        """loads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plgn in msg.data:
            self.bot.load_plugin_file(plgn)
        return msg.reply(text="loaded plugin(s) " + msg.text)

    @command(admin=True)
    def pluginunload(self, msg):
        """unloads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plgn in msg.data:
            self.bot.unload_plugin(plgn)
        return msg.reply(text="unloaded plugin(s) " + msg.text)

    @command(admin=True)
    def pluginreload(self, msg):
        """reloads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plgn in msg.data:
            self.bot.unload_plugin(plgn)
            self.bot.load_plugin_file(plgn)
        return msg.reply(text="reloaded plugin(s) " + msg.text)

    @command(admin=True)
    def exit(self, msg):
        """exits the bot, admin only"""
        self.bot.loop.stop()

    @command(admin=True)
    def sync(self, msg):
        """syncs the bot, admin only"""
        self.bot.sync()
