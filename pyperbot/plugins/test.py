from pyperbot.wrappers import plugin, command


@plugin
class foo:
    @command
    def test(self, msg):
        return msg.reply(text="test worked!")

    @command
    def error(self, msg):
        raise Exception("foo bar baz")
