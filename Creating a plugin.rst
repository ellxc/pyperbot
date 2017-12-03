Creating a plugin
=================

a plugin object can be any class wrapped in the @plugin wrapper::

    @plugin
    class foo:
        def __init__(self, bot, config):
            ...

when loaded it's members are inspected for plugin features. The
possible features and when they will be called are as follows:

:onload: after the plugin has been
    initialised. this is a useful place to load resources or start
    threads etc.
    ::

        @onload
        def load_file(self):
            ...

:unload: before the plugin instance
    is unloaded and deleted. useful releasing resources and saving
    state. 
    ::

        @unload
        def save_file(self):
            ...

:sync: when the bot is about to be shutdown or manually via the ``#sync``
    admin command. useful for saving state. 
    ::

        @sync
        def backup(self):
            ...

:cron: at regular timed intervals as denoted by the specified cron.
    ::

        @cron('*/5 * * * *')  # run every 5 minutes
        def update(self):
            ...

:event: when the event manager triggers the specified event.
    ::

        @event('001')
        def onConnect(self, message):
            ...

:trigger: when the specified trigger is evaluated to be true.
    ::

        @trigger(lambda msg: msg.text.startswith("foo"))
        def onFoo(self, msg):
            ...

:regex: when the PRIVMSG text matches the specified regex
    ::

        @regex(r'fooo+')
        def onFooo(self, msg, match)
            ...

:command: when the command matches the optionally specified name
    or the name of the command functions
    ::

        @command
        def foo(self, msg):
            ...

        @command('bar')
        def baz(self, msg):
            ...

:pipeinable_command: another type of command, this will be called
    for every piped-in message object. the arguments it is called with
    are stored in a message object which will be the first parameter.

    ::

        @pipeinable_command
        def something(self, initial, each):
            ...

:complexcommand: yet another type of command that allows the use of
    coroutines for advanced behaviours. this must follow this pattern,
    replacing the ellipses with your intended functionality.
    ::

        @complexcommand
        async def foo(self, initial, inpipe, outpipe):
            ... # setup
            try:
                while 1:
                    msg = await inpipe.recv()
                    ... # for each message piped in
            except PipeClosed:
                ... # after the last message has been piped in
            finally:
                outpipe.close()
                inpipe.close()


