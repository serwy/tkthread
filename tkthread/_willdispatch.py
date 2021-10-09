#
# Copyright 2021 Roger D. Serwy
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
_willdispatch.py


This Tkinter multithreading support makes use of the undocumented
`.willdispatch()` function that then bypasses the `WaitForMainloop()`
C function in _tkinter.c.

The C code already checks the running thread and serializes the
request to the main thread with `Tkapp_ThreadSend()`. That
function acquires a mutex before adding the event to the Tcl event queue.

There is a threading race condition, where `disptaching` can be set to
zero before the thread reads it. This is why there is a retry loop on
the function call.

"""
from __future__ import print_function
import traceback
import sys

from . import tk

class _tk_dispatcher(object):
    """ Force `WaitForMainloop` to return 1"""
    _RETRY_COUNT = 10

    def __init__(self, tk):
        self.__tk = tk

    def __getattr__(self, name):
        return getattr(self.__tk, name)


    # ---------------------------
    # create the needed functions
    # ---------------------------

    def _make_func(name):
        def wrapped(self, *args, **kwargs):
            _tk = self.__tk
            func = getattr(_tk, name)
            rcount = _tk_dispatcher._RETRY_COUNT
            for n in range(rcount + 1):
                _tk.willdispatch()
                try:
                    result = func(*args, **kwargs)
                    break
                except RuntimeError as exc:
                    # There is a race condition between this thread
                    # and the main thread event loop setting dispatch=0.
                    # As rare as the condition is, it needs to be handled.
                    if n < rcount:
                        traceback.print_exc(file=sys.stderr)
                        print('retrying %r %i of %i' % (name, n+1, rcount),
                              file=sys.stderr)
                        continue
                    else:
                        raise
            return result
        return wrapped


    _locals = locals()
    for _name in ['call', 'createcommand', 'deletecommand',
                  'setvar', 'unsetvar', 'getvar',
                 'globalsetvar', 'globalunsetvar', 'globalgetvar']:
        _locals[_name] = _make_func(_name)

    del _locals
    del _name
    del _make_func


class _Tk(tk.Tk):
    def __init__(self, *args, **kw):
        tk._Tk_original_.__init__(self, *args, **kw)
        # patch the existing Tkapp object
        self.tk = _tk_dispatcher(self.tk)


def tkinstall():
    """Replace tkinter's `Tk` class with a thread-enabled version"""
    import platform
    runtime = platform.python_implementation()
    if 'cpython' not in runtime.lower():
        raise RuntimeError('Requires CPython, not %s' % runtime)

    tk.__dict__.setdefault('_Tk_original_', tk.Tk)  # save the original version
    if tk.Tk is tk._Tk_original_:
        tk.Tk = _Tk


def main(widget):
    """Decorator to run callable on Tcl/Tk mainthread."""
    def wrapped(func):
        widget.tk.willdispatch()
        widget.after(0, func)
        return func
    return wrapped


def current(widget):
    """Decorator to run callable on the current thread.
        Useful for quickly changing with `tkthread.main`"""
    def wrapped(func):
        func()
        return func
    return wrapped
