import Countdown.solver as cd
from pyperbot.wrappers import plugin, command, onload, cron, sync, unload
from random import sample, randint
from collections import defaultdict
from asyncio import Future, TimeoutError
import async_timeout
import ast
import operator as op
import shelve

standard_big = [25, 50, 75, 100]
standard_small = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10]


operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.USub: op.neg}


class IncorrectNumbers(Exception):
    def __init__(self, n):
        self.n = n
        super().__init__()


def eval_expr(expr, numbers):
    try:
        return eval_(ast.parse(expr, mode='eval').body, numbers)
    except SyntaxError:
        raise Exception("failed to parse attempt")


def check_expr(n, numbers):
    def find_nums(node):
        if isinstance(node, ast.Num):  # <number>
            return [node.n]
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return find_nums(node.left) + find_nums(node.right)
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return find_nums(node.operand)

    def check_counts(a, b):
        all(a.count(x) <= b.count(x) for x in a)

    return check_counts(find_nums(n), numbers)
    
def eval_(node, numbers):
    if not check_expr(node, numbers):
        raise Exception("nah m8")
    if isinstance(node, ast.Num):  # <number>
        if node.n in numbers:
            return node.n
        else:
            raise IncorrectNumbers(node.n)
    elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
        return operators[type(node.op)](eval_(node.left, numbers), eval_(node.right, numbers))
    elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
        return operators[type(node.op)](eval_(node.operand, numbers))
    else:
        raise Exception("failed to parse attempt")


@plugin
class Countdown:
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.store = {}
        if 'filename' in self.config:
            self.filename = self.config['filename']
        else:
            self.filename = "./countdownscore.shelf"

        self.inprogress = defaultdict(lambda: defaultdict(lambda: False))

    @onload
    def onload(self):
        self.store = shelve.open(self.filename, writeback=True)

    @cron("*/10 * * * *")
    @sync
    def save(self):
        self.store.sync()

    @unload
    def unload(self):
        self.store.close()

    @command('score')
    def cdscore(self, msg):
        if not msg.data:
            d = self.store.get(msg.server, {}).get(msg.nick, 0)
            l = lambda data: "%s: your countdown score is %d" % (msg.nick, data)
        else:
            d = {nick: self.store.get(msg.server, {}).get(nick, 0) for nick in msg.data}
            l = lambda data: "countdown score: " + ", ".join("%s: %d" % (nick, karma) for nick, karma in data.items())
        return msg.reply(data=d, str_fn=l)

    @command('solve', rate_limit_no=1, rate_limit_period=30)
    def cdsolve(self, msg):
        print(msg.data)
        target = int(msg.data[0])
        numbers = list(map(int, msg.data[1:7]))
        solution, result = cd.solve(target, numbers)
        msgstr = "{} = {}"
        if not result == target:
            msgstr = "closest solution: " + msgstr
        return msg.reply(msgstr.format(solution, result))

    @command('solvebest', rate_limit_no=1, rate_limit_period=30)
    def cdsolvebest(self, msg):
        print(msg.data)
        target = int(msg.data[0])
        numbers = list(map(int, msg.data[1:7]))
        solution, result = cd.solve_best(target, numbers)
        msgstr = "{} = {}"
        if not result == target:
            msgstr = "closest solution: " + msgstr
        return msg.reply(msgstr.format(solution, result))

    @command('countdown')
    async def countdown(self, msg):
        if not self.inprogress[msg.server][msg.params]:
            self.inprogress[msg.server][msg.params] = True
            numbers = sample(standard_big, 2) + sample(standard_small, 4)
            target = randint(1, 999)

            yield msg.reply("game starting. The numbers are {}. The target is {}. you have 1 minute. go!"
                            .format(" ".join(str(n) for n in numbers), target))

            attempts = []
            done = Future(loop=self.bot.loop)

            def attempt_handler(message):
                if message.params == msg.params:
                    try:
                        result = eval_expr(message.text, numbers)
                        attempts.append((result, message))
                        if result == target:
                            done.set_result(message)
                        else:
                            self.bot.send(msg.reply("Answer submitted"))
                    except IncorrectNumbers as e:
                        self.bot.send(msg.reply("Incorrect number used: {}".format(e.n)))
                    except Exception as e:
                        print(e)

            try:
                self.bot.clients[msg.server].em.register_handler('PRIVMSG', attempt_handler)
                async with async_timeout.timeout(60):
                    await done
                    winner = done.result().nick
                    server = done.result().server
                    self.store.setdefault(server, {})
                    self.store[server].setdefault(winner, 0)
                    self.store[server][winner] += 10
                    yield msg.reply("we have a winner! {0} wins! 10 points to {0}dor!".format(done.result().nick))
            except TimeoutError:
                if attempts:
                    closest = None
                    closestmsg = None
                    for r, a in attempts:
                        if closest is None or abs(r-target) < abs(closest-target):
                            closest = r
                            closestmsg = a
                    if abs(closest-target) < 10:
                        points = 10 - abs(closest-target)
                        winner = closestmsg.nick
                        server = closestmsg.server
                        if server not in self.store:
                            self.store[server] = {}
                        if winner not in self.store[server]:
                            self.store[server][winner] = 0
                        self.store[server][winner] += points
                        pointstr = "{} away! {} points to {}dor!".format(abs(closest-target), points, winner)
                    else:
                        pointstr = "too far away to win any points :("

                    yield msg.reply("closest attempt is {} = {} made by {}. {}"
                                    .format(closestmsg.text, closest, closestmsg.nick, pointstr))
                else:
                    yield msg.reply("Times up! No attempts were made.")

                yield msg.reply("solving...")
                solution, result = cd.solve(target, numbers)
                msgstr = "solution: {} = {}"
                if not result == target:
                    msgstr = "closest " + msgstr
                yield msg.reply(msgstr.format(solution, result))
            finally:
                self.bot.clients[msg.server].em.deregister_handler('PRIVMSG', attempt_handler)
                self.inprogress[msg.server][msg.params] = False
