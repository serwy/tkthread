"""
tkthread - calling the Tcl/Tk event loop
           with Python multi-threading

Versions - CPython 2.7/3.x, PyPy 2.7/3.x

Roger D. Serwy
2018-03-23

Synopsis
--------

The `tkthread` module easily allows Python threads
to interact with Tk.


Background
----------

The Tcl/Tk language is shipped with Python, and follows a
different threading model than Python itself which can
raise obtuse errors when mixing Python threads with Tk, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError: Call from another thread

Tcl can have many isolated interpreters running, and are
tagged to a particular OS thread. Calling a Tcl interpreter
from a different thread raises the apartment error.

The _tkinter module detect if a Python thread is different
from the Tcl interpreter thread, and then waits one second
to acquire a lock on the main thread. If there is a time-out,
a RuntimeError is raised.

Usage
-----

The `tkthread` module provides the `TkThread` class,
which can synchronously interact with the main thread.

    import time
    import threading

    def run(func):
        threading.Thread(target=func).start()

    from tkthread import tk, TkThread

    root = tk.Tk()
    root.wm_title('initializing...')

    tkt = TkThread(root)  # make the thread-safe callable

    run(lambda: root.wm_title('FAILURE'))
    run(lambda: tkt(root.wm_title, 'SUCCESS'))

    root.update()
    time.sleep(2)  # _tkinter.c:WaitForMainloop fails
    root.mainloop()

There is an optional `.install()` method on `TkThread` which
intercepts Python-to-Tk calls. This must be called on the
default root, before the creation of child widgets. There is
a slight performance penalty for Tkinter widgets that operate only
on the main thread.


Legal
-----

Copyright 2018 Roger D. Serwy

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
import functools
import threading
import sys

# 2/3 compatibility
if sys.version < '3':
    import Tkinter as tk
    import Queue as queue
    _main_thread = threading.current_thread()

else:
    import tkinter as tk
    import queue
    _main_thread = threading.main_thread()

from ._version import __version__

__all__ = ['TkThread', 'tk', 'Result', '__version__']

class Result(object):
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
            raise RuntimeError(repr(self.result))
        else:
            return self.result

class _TkIntercept(object):
    """ wrapper to a _tkinter.tkapp object """

    # set of functions to intercept
    _intercept = set(['call', 'createcommand',
                      'setvar','globalsetvar',
                      'getvar', 'globalgetvar',
                      'unsetvar', 'globalunsetvar'
                      ])

    def __init__(self, tk, tkt):
        object.__setattr__(self, '__tk__', tk)
        object.__setattr__(self, '__tkt__', tkt)

        lookup = {}
        for name in self._intercept:
            what = getattr(tk, name)
            lookup[name] = functools.partial(tkt, what)

        object.__setattr__(self, '__lookup__', lookup)

    def __getattr__(self, name):
        ret = self.__lookup__.get(name, None)
        if ret is None:
            return getattr(self.__tk__, name)
        else:
            return ret

    def __setattr__(self, name, value):  # FIXME: needed?
        if name in self._intercept:
            raise AttributeError('%s is read-only' % name)
        object.__setattr__(self, name, value)


class TkThread(object):
    def __init__(self, root):

        if hasattr(root, 'tkt'):
            raise RuntimeError('already installed')
        root.tkt = self

        if threading.current_thread() is not _main_thread:
            raise RuntimeError('Must be started from main thread')
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
        """Redirect tk.call instead"""
        # there is a performance penalty for main-thread-only code
        if self.root.children:
            raise RuntimeError('root can not have children')
        new_tk = _TkIntercept(self.root.tk, self)
        self.root.tk = new_tk

    def _call_from(self):
        # This executes in the main thread, called from the Tcl interpreter
        func, args, kwargs, tres = self._call_from_data.pop(0)
        try:
            error = False
            result = func(*args, **kwargs)
        except BaseException as exc:
            error = True
            result = exc

        if tres:
            self._results.remove(tres)
            tres.set(result, error)

    def _tcl_thread(self):
        # Operates in its own thread, with its own Tcl interpreter

        tcl = tk.Tcl()
        tcl.eval('package require Thread')

        command = 'thread::send  %s "%s"' % (self._main_thread_id,
                                             self._call_from_name)
        while self._running:
            func = self._thread_queue.get()
            if func is None:
                break
            self._call_from_data.append(func)
            tcl.eval(command)

    def __call__(self, func, *args, **kwargs):
        """Apply args and kwargs to function and return its result"""
        if threading.current_thread() is _main_thread:
            return func(*args, **kwargs)
        else:
            tres = Result()
            self._results.add(tres)
            self._thread_queue.put((func, args, kwargs, tres))
            return tres.get()

    def nosync(self, func, *args, **kwargs):
        """Non-blocking, no-synchronization call"""
        self._thread_queue.put((func, args, kwargs, None))

    def destroy(self):
        """Destroy the root object"""
        while self._results:
            tr = self._results.pop()
            tr.set('destroying', is_error=True)
        self._running = False
        self._thread_queue.put(None)
        self.root.destroy()

