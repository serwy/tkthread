"""
tkthread - calling the Tcl/Tk event loop
           with Python multi-threading

Versions - CPython 2.7/3.x, PyPy 2.7/3.x

Roger D. Serwy
2018-03-23


Background
----------

The Tcl/Tk language is shipped with Python, and follows a
different threading model than Python itself which can
raise obtuse error when mixing Python threads with Tk, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError('Call from another thread',)

Tcl can have many isolated interpreters running, and are
tagged to a particular system thread. Calling a Tcl interpreter
from a different thread raises the apartment error.

Usage
-----

The `tkthread` module provides `tkt`, a callable instance of
`TkThread` which synchronously interacts with the main thread.

    text.insert('end-1c', 'some text')       # fails
    tkt(text.insert, 'end-1c', 'some text')  # succeeds


Other
-----

If you receive the following error:

    RuntimeError: Tcl is threaded but _tkinter is not

then your binaries are built with the wrong configuration flags.


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


__all__ = ['TkThread', 'tk', 'tkt', 'Result']

class Result(object):
    """Cross-thread synchronization"""
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


class TkThread(object):
    def __init__(self, root):
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
        self.root.destroy()
        self._running = False
        self._thread_queue.put(None)


_root = tk.Tk()
_root.withdraw()
tkt = TkThread(_root)
