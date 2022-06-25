#
# Copyright 2018, 2021 Roger D. Serwy
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
tkthread
--------

Easy multithreading with Tkinter on CPython 2.7/3.x and PyPy 2.7/3.x.


Background
----------

Multithreading with `Tkinter` can often cause the following errors:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError: Call from another thread

This module allows Python multithreading to cooperate with Tkinter.


Experimental Usage CPython
--------------------------

For CPython 2.7/3.x, `tkhread.tkinstall()` can be called first,
and will patch Tkinter to re-route calls to the main thread,
using the "willdispatch" internal API call.

    import tkthread; tkthread.tkinstall()
    import tkinter as tk

    root = tk.Tk()

    import threading
    def thread_run(func): threading.Thread(target=func).start()

    @thread_run
    def func():
        root.wm_title('WORKS')
        print(threading.current_thread())

        @tkthread.main(root)    # run on main thread
        @tkthread.current(root) # run on current thread
        def testfunc():
            tk.Label(text=threading.current_thread()).pack()

    root.mainloop()

Usage CPython/Pypy
------------------

The `tkthread` module provides the `TkThread` class,
which can synchronously interact with the main thread.

    from tkthread import tk, TkThread

    root = tk.Tk()        # create the root window
    tkt = TkThread(root)  # make the thread-safe callable

    import threading, time
    def run(func):
        threading.Thread(target=func).start()

    run(lambda:     root.wm_title('FAILURE'))
    run(lambda: tkt(root.wm_title,'SUCCESS'))

    root.update()
    time.sleep(2)  # _tkinter.c:WaitForMainloop fails
    root.mainloop()


There is an optional `.install()` method on `TkThread` which
intercepts Python-to-Tk calls. This must be called on the
default root, before the creation of child widgets. There is
a slight performance penalty for Tkinter widgets that operate only
on the main thread.
"""
import functools
import threading
import sys

# 2/3 compatibility
if sys.version < '3':
    import Tkinter as tk
    import Queue as queue
else:
    import tkinter as tk
    import queue

from ._version import __version__
from ._willdispatch import (
    tkinstall, main, current,
    call, call_nosync,
    called_on_main
    )

__all__ = [
    'TkThread', 'tk', '__version__',
    'tkinstall', 'patch', 'main', 'current',
    'call', 'call_nosync',
    ]

patch = tkinstall  # Issue #4


class _Result(object):
    """Cross-thread synchronization of a result"""
    def __init__(self):
        self.event = threading.Event()
        self.result = None
        self.is_error = False

    def set(self, result, is_error=False):
        self.result = result
        self.is_error = is_error
        self.event.set()

    def get(self):
        self.event.wait()
        if self.is_error:
            exc_type, exc_value, tb = self.result
            raise exc_type(exc_value)
        else:
            return self.result


class _TkIntercept(object):
    """wrapper to a _tkinter.tkapp object """

    def __init__(self, tk, tkt):
        self.__tk = tk
        self.__tkt = tkt

    def __getattr__(self, name):
        # every member of .tkapp is callable
        func = getattr(self.__tk, name)
        return functools.partial(self.__tkt, func)


class TkThread(object):
    def __init__(self, root):
        """TkThread object for the root 'tkinter.Tk' object"""

        self._main_thread = threading.current_thread()
        self.root = root
        self.root.eval('package require Thread')
        self._main_thread_id = self.root.eval('thread::id')

        self._call_from_data = []  # for main thread
        self._call_from_name = self.root.register(self._call_from)
        self._thread_queue = queue.Queue()
        self._results = set()

        self._running = True
        self._th = threading.Thread(target=self._tcl_thread)
        self._th.daemon = True
        self._th.start()

    def install(self):
        """Automatically redirect Python-to-Tk calls"""
        # there is a performance penalty for main-thread-only code
        if self.root.children:
            raise RuntimeError('root can not have children')
        new_tk = _TkIntercept(self.root.tk, self)
        self.root.tk = new_tk
        return self

    def _call_from(self):
        # This executes in the main thread, called from the Tcl interpreter
        func, args, kwargs, tres = self._call_from_data.pop(0)
        try:
            error = False
            result = func(*args, **kwargs)
        except BaseException as exc:
            error = True
            result = sys.exc_info()
            raise  # show the error
        finally:
            if tres:
                tres.set(result, error)
                self._results.discard(tres)

    def _tcl_thread(self):
        # Operates in its own thread, with its own Tcl interpreter

        tcl = tk.Tcl()
        tcl.eval('package require Thread')

        command = 'thread::send  %s "%s"' % (self._main_thread_id,
                                             self._call_from_name)
        while self._running:
            item = self._thread_queue.get()
            if item is None:
                break
            self._call_from_data.append(item)
            tcl.eval(command)

    def __call__(self, func, *args, **kwargs):
        """Apply args and kwargs to function and return its result"""
        if threading.current_thread() is self._main_thread:
            return func(*args, **kwargs)
        else:
            tres = _Result()
            self._results.add(tres)
            self._thread_queue.put((func, args, kwargs, tres))
            return tres.get()

    def nosync(self, func, *args, **kwargs):
        """Non-blocking, no-synchronization call"""
        self._thread_queue.put((func, args, kwargs, None))

    def flush(self):
        """Flush all .nosync calls"""
        self(int)  # a basic callable to put on the queue

    def destroy(self):
        """Destroy the TkThread object.

        Threads that call into TkThread must be stopped
        before calling .destroy() to avoid missing pending
        calls from being set to error.
        """
        self._running = False
        self._thread_queue.put(None)  # unblock _tcl_thread queue
        while self._results:
            try:
                tr = self._results.pop()
                tr.set((RuntimeError, 'destroyed', None),
                       is_error=True)
            except KeyError:
                pass
