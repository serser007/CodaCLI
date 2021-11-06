from collections import deque
from threading import Thread
from time import sleep


class ThreadPool(Thread):
    def __init__(self, max_threads=10, max_awaiting=10):
        super(ThreadPool, self).__init__(daemon=True)
        self._max_threads = max_threads
        self._threads = 0
        self._actions = deque()
        self._tags = dict()
        self._max_awaiting = max_awaiting
        super().start()

    def _f(self, f):
        try:
            f[0](*f[1])
        except:
            pass

        self._tags[f[2]] -= 1
        self._threads -= 1

    def count(self, tag=""):
        if tag not in self._tags.keys():
            return 0
        return self._tags[tag]

    def run(self):
        while True:
            while self._threads < self._max_threads and len(self._actions) > 0:
                self._threads += 1
                action = self._actions.pop()
                thread = Thread(target=self._f, args=[action], daemon=True)
                thread.start()

    def add_thread(self, f, args=(), tag=""):
        if tag not in self._tags.keys():
            self._tags[tag] = 1
        else:
            self._tags[tag] += 1
        self._actions.append((f, args, tag))

        while len(self._actions) == self._max_awaiting:
            sleep(0.1)
