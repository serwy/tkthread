import unittest
import threading
import time

import tkthread


def run(func, args=(), kwargs=None, name=None):
    th = threading.Thread(target=func, args=args, kwargs=kwargs,
                          name=name)
    th.daemon = True
    th.start()
    return th


def thread_start(*args, **kwargs):
    """Decorator that returns a started thread running the function."""
    def decorator(func):
        th = run(func, args, kwargs, name='thread_start')
        return th
    return decorator


def call_until(timeout=None):
    """Decorator that returns if a call has timed out."""
    t = time.time()

    def decorator(func, timeout=timeout):
        while func():
            if timeout is not None:
                if time.time() - t >= timeout:
                    return True
        return False
    return decorator


class ExpectedTestError(Exception):
    pass


class TestResultClass(unittest.TestCase):

    def test_event(self):
        r = tkthread._Result()
        self.assertEqual(r.event.is_set(), False)

    def test_set_result(self):
        r = tkthread._Result()
        self.assertEqual(r.result, None)

        @thread_start(r)
        def tset(r):
            r.set(True, is_error=False)
        tset.join()

        self.assertEqual(r.result, True)

    def test_set_error(self):
        r = tkthread._Result()

        @thread_start(r)
        def tset(r):
            r.set((RuntimeError, 'testing', None),
                  is_error=True)
        tset.join()

        with self.assertRaises(RuntimeError):
            r.get()

    def test_wait(self):
        r = tkthread._Result()
        done = []

        @thread_start(r)
        def twait(r):
            result = r.get()
            done.append(result)

        self.assertEqual(r.event.is_set(), False)
        self.assertFalse(done)

        r.set(None)
        self.assertEqual(r.event.is_set(), True)

        twait.join()  # wait for thread to finish
        self.assertIs(done[0], None)


class TestTkThread(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tkthread.tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        cls.root = None

    def setUp(self):
        self.had_error = False
        self.tkt = tkthread.TkThread(self.root)

    def tearDown(self):
        self.tkt.destroy()

    def test_init_from_thread(self):

        @thread_start(self)
        def tstart(self):
            try:
                tkthread.TkThread(self.root)
            except RuntimeError:
                self.had_error = True

        tstart.join(5.0)
        self.assertFalse(tstart.is_alive())
        self.assertTrue(self.had_error)

    def test_call(self):

        @thread_start(self)
        def tstart(self):
            try:
                self.tkt(self.root.wm_title, 'SUCCESS')
            except RuntimeError:
                self.had_error = True

        while tstart.is_alive():
            self.root.update()

        self.assertFalse(self.had_error)

    def test_no_wrap(self):
        # Sanity check.
        # If this test fails, then something has changed with Tkinter

        @thread_start(self)
        def tstart(self):
            try:
                self.root.wm_title('FAIL')
            except RuntimeError:
                self.had_error = True

        time.sleep(2)  # relies on _tkinter.c behavior
        self.assertTrue(self.had_error)

    def test_call_error(self):
        # This test will cause a traceback to display

        @thread_start(self)
        def tstart(self):
            def errorfunc():
                raise ExpectedTestError('expected in Tkinter callback')
            try:
                self.tkt(errorfunc)
            except ExpectedTestError:
                self.had_error = True

        while tstart.is_alive():
            self.root.update()  # process the event

        self.assertTrue(self.had_error)

    def test_install(self):
        _orig_tk = self.root.tk
        self.tkt.install()

        @thread_start(self)
        def tstart(self):
            try:
                self.root.eval('')
            except RuntimeError:
                self.had_error = True
                raise

        time.sleep(2)  # relies on _tkinter.c behavior

        while tstart.is_alive():
            self.root.update()

        self.assertFalse(self.had_error)
        self.root.tk = _orig_tk  # "tkt.uninstall"

    def test_install_children(self):
        _orig_tk = self.root.tk

        text = tkthread.tk.Text(self.root)
        with self.assertRaises(RuntimeError):
            self.tkt.install()

        del text
        self.root.tk = _orig_tk  # in case test failed

    def test_call_main(self):
        # call from the main thread immediately
        with self.assertRaises(tkthread.tk.TclError):
            self.tkt(self.root.eval, '-')
        self.tkt(self.root.eval, '')

    def test_nosync(self):

        ev_nosync = threading.Event()
        ev = threading.Event()

        @thread_start(self, ev_nosync)
        def nosync(self, ev_nosync):
            self.tkt.nosync(ev_nosync.set)

        nosync.join(5.0)
        self.assertFalse(nosync.is_alive())

        @thread_start(ev)
        def wait_thread(ev):
            ev.wait()

        @thread_start(self, ev)
        def set_ev(self, ev):
            self.tkt(ev.set)

        while wait_thread.is_alive():
            self.root.update()

        self.assertTrue(ev_nosync.is_set())

    def test_destroy(self):

        @thread_start(self)
        def block(self):
            # root.update not called, so .tkt will block
            try:
                self.tkt(lambda: None)
            except RuntimeError:
                self.has_error = True

        @call_until(4)
        def wait_tkt():
            # need to wait for the .tkt call to execute
            # so that the Result object can be set by .destroy
            return not bool(self.tkt._call_from_data)

        self.assertFalse(wait_tkt)

        self.tkt.destroy()

        block.join(5.0)
        self.assertFalse(block.is_alive())
        self.assertTrue(self.has_error)


if __name__ == '__main__':
    unittest.main()
