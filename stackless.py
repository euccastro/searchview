from collections import deque
from greenlet import greenlet
import traceback

__all__ = ['tasklet', 'schedule', 'channel', 'getruncount', 'run']

def hexid(x):
    return hex(id(x))

class tasklet(object):
    def __init__(self, fn):
        self.fn = fn
        self.alive = False
        self.channel_data = None
        self.blocked = False
    def __call__(self, *args, **kw):
        self.alive = True
        self.greenlet = greenlet(lambda: self.run(*args, **kw),
                                 parent=_base.greenlet)
        _scheduled.append(self)
    def run(self, *args, **kw):
        fn = self.fn
        del self.fn
        fn(*args, **kw)
        self.alive = False

def _task_from_greenlet(greenlet):
    ret = tasklet(None)
    ret.alive = True
    ret.greenlet = greenlet
    del ret.fn
    return ret

def _switch(task):
    assert not task.blocked
    global _current
    _current = task
    task.greenlet.switch()

def schedule():
    _scheduled.append(_current)
    _resume_next()

def _resume_next():
    while _scheduled:
        next = _scheduled.popleft()
        if not next.alive:
            continue
        _switch(next)
        break

class channel(object):
    class _bomb(object):
        def __init__(self, exc_type, exc_val, exc_tb):
            self.type = exc_type
            self.val = exc_val
            self.tb = exc_tb
        def raise_(self):
            raise self.type, self.val, self.tb

    def __init__(self):
        self.receivers = deque()
        self.senders = deque()

    def _get_balance(self):
        return len(self.senders) - len(self.receivers)
    balance=property(_get_balance)

    def send_exception(self, exc_type, exc_val=None, exc_tb=None):
        self.send(self._bomb(exc_type, exc_val, exc_tb))

    def send(self, data):
        hexid = lambda x: hex(id(x))
        _current.channel_data = data
        self.senders.append(_current)
        if self.receivers:
            tasklet(_resume)(self.receivers.popleft())
        _block()

    def receive(self):
        hexid = lambda x: hex(id(x))
        block = not self.senders
        if block:
            self.receivers.append(_current)
            _block()
        sender = self.senders.popleft()
        data = sender.channel_data
        if block:
            sender.blocked = False
            _scheduled.append(sender)
        else:
            _resume(sender)
        if isinstance(data, self._bomb):
            data.raise_()
        else:
            return data

def _block():
    _current.blocked = True
    _resume_next()

def _resume(task):
    task.blocked = False
    _scheduled.appendleft(task)
    schedule()

def getruncount():
    return len(_scheduled)

def run():
    global _base
    _base = _current
    while getruncount() > 0:
        schedule()

_scheduled = deque()
_current = _base = _task_from_greenlet(greenlet.getcurrent())

def test():
    ch = channel()
    def f():
        print "colho"
        print ch.receive()
        print "colhido"

    def g():
        print "mando"
        ch.send("esto")
        print "mandado"

    tasklet(g)()
    tasklet(f)()
    run()
    print "dun"

def test2():
    import time

    ch = channel()
    def f():
        print "espero"
        start = time.time()
        while time.time() - start < 10:
            schedule()
        print "mando"
        ch.send(5)
        print "mandei"

    def g():
        print "recevo"
        print ch.receive()
        print "recevido"

    tasklet(f)()
    tasklet(g)()
    print "vamos"
    run()
    print "dun"

def test3():
    import time

    ch = channel()
    def f():
        print "espero"
        start = time.time()
        while time.time() - start < 10:
            schedule()
        print "recevo"
        print ch.receive()
        print "recevido"

    def g():
        print "mando"
        ch.send(5)
        print "mandei"

    tasklet(f)()
    tasklet(g)()
    print "vamos"
    run()
    print "dun"

