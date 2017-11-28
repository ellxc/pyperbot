from wrappers import plugin, command


@plugin
class admin:
    @command(admin=True)
    def pluginload(self, msg):
        """loads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plugin in msg.data:
            self.bot.load_plugin_file(plugin)
        return msg.reply(text="loaded plugin(s) " + msg.text)

    @command(admin=True)
    def pluginunload(self, msg):
        """unloads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plugin in msg.data:
            self.bot.unload_plugin(plugin)
        return msg.reply(text="unloaded plugin(s) " + msg.text)

    @command(admin=True)
    def pluginreload(self, msg):
        """reloads a plugin, admin only"""
        if not msg.data:
            return msg.reply(text="please specify a plugin")
        for plugin in msg.data:
            self.bot.unload_plugin(plugin)
            self.bot.load_plugin_file(plugin)
        return msg.reply(text="reloaded plugin(s) " + msg.text)

    @command(admin=True)
    def exit(self, msg):
        """exits the bot, admin only"""
        self.bot.loop.stop()

    @command(admin=True)
    def sync(self, msg):
        """syncs the bot, admin only"""
        self.bot.sync()
