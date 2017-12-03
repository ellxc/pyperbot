========
pyperbot
========
An Asynchronous multi-server irc bot written in Python.
-------------------------------------------------------
Pre-requisites
~~~~~~~~~~~~~~

* **Python** >3.6
* **Seval** for a sandboxed python interpreter
* **python-dateutil** for reminders
* **pyparsing** for the shell parser
* **crontab** for setting timed jobs
* **patience** it might not work completely...

Installing
~~~~~~~~~~

1. clone the project to a directory
2. run ``pip install -e . -r requirements.txt`` in the directory

Running
~~~~~~~
1. edit the **settings.json** file
2. run ``python3 -m pyperbot.bot settings.json``

Piping:
-------
The main feature of this bot is it's shell style piping of
commands. For example::

    #echo Hello World! | sed s/world/You
    Hello You!

Seval
-----
Another main feature of the bot is its environment variables
and the ability to use python syntax through a plugin called
seval. This allows safe arbitrary code to be run in an irc
channel as well as giving the ability to store settings or
similar inside one's own 'self'. Plugins can also expose data
into the enviroment for use in commands.

when invoked seval will also have a reference to the message
piped into it or the invoking message, this can be accessed
through the name ``msg``. This object has several fields that
can be of use:

:text: this is the string representation of the message's payload
:data: this is message's payload
:nick: the nickname of the user
:params: the parameters of the message, in this case usually the channel it was sent to
:user: the username of the user
:domain: the domain of the user
:timestamp: a datetime object set to the time the message was sent

Aliases
-------
These allow you to save a very long command as a much shorter
one. as well as allow a command to take arguments. ::

    #alias glue = echo !:0 is now glued to !:1
    #glue gary 'the ceiling'
    gary is now glued to the ceiling

The syntax for arguments is !:index or !:start:stop:step.
when wanting a range of arguments it is possible to not specify
one of the parameters, much like a slice in python.

``!:0``     will give you the first argument

``!::``     will give you all arguments passed in

``!:0:``    will give you all but the first

``!::-1``   will give you all but the last

``!:::-1``  will give you the arguments in reverse order

Message Buffer
--------------
previous non-bot messages are stored in a buffer. this buffer is
by default limited to 20 messages per channel. The syntax for
accessing this buffer is ``!^index:nick`` again it is possible to
not specify either. the nick parameter will filter the buffer to
only contain messages from that nick, if not specified the buffer
will not be filtered. the index parameter will specify which
previous message to return, if not specified the default is 1.

``!^``     will return the text of the previous non-bot message

``!^gary``  will return the previous message made by gary

``!^3``     will return the text of the third last non-bot message

Enviroment Variables
--------------------
These can be reached either by name in a seval command, or by
using the ``$var`` syntax. There are also userspaces to allow
for read only variables that only that nick can modify, these
can be reached by using the ``~user`` syntax or accessing it
through the variable ``self``.
variables can also be access using brackets, like so ``$(foo bar)``
this will access the variable "foo bar" which contains a space,
so would otherwise be tricky to access

Subcalls
--------
inside a pipeline you can also make subcalls using backticks::

    echo `echo foo`
    foo

Starred
-------
a lot of these subsitutions will return data in lists or other
collections, which might be annoying to actually use in commands.
this is why you can use * to unwrap a collection. ::

    #> a = [1,2,3]
    #echo $a
    [1, 2, 3]

    #echo *$a
    1 2 3

    #> a = [[1,2,3]]
    #echo **$a
    1 2 3

Strings
-------
not all strings were created equal. strings denoted by ' are
normal strings, but strings denoted by " are strings that can
contain special goodness. They support variable substitution
with both the $ and ~ syntax, message buffer access, argument
passing and the starred syntax. ::

    #> a = "bar"
    #echo "foo $a baz"
    'foo bar baz'

    #> a = ["this", "is", "some", "data"]
    #echo "*$a"
    'this is some data'

