import time
import queue
import unittest as ut
import multiprocessing as mp

NPROCESSES = 5

class TestProcess(mp.Process):
    """
    """

    def __init__(self):
        super().__init__()
        self.started = mp.Value('i', 0)
        self.iq = mp.Queue()
        self.oq = mp.Queue()

    def run(self):
        while self.started.value:
            try:
                item = self.iq.get(block=False)
                self.oq.put(item)
            except queue.Empty:
                pass
            continue
        return

    def start(self):
        self.started.value = 1
        super().start()
        return

    def join(self):
        self.started.value = 0
        super().join()
        return

class TestMultiprocessingFunction(ut.TestCase):
    """
    """

    def test_forking_multiple_processes(self):
        """
        """

        children = [TestProcess() for i in range(NPROCESSES)]

        # start the child processes
        for p in children:
            p.start()

        # pass an object throught the queues
        for p in children:
            p.iq.put('Hello World!')
            item = p.oq.get()

        # join the child processes
        for p in children:
            p.join()

if __name__ == '__main__':
    ut.main()
