#
# Copyright 2021, 2022 Roger D. Serwy
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

There is a threading race condition, where `dispatching` can be set to
zero before the thread reads it. This is why there is a retry loop on
the function call.

"""
from __future__ import print_function
import traceback
import sys
import threading
try:
    import queue
except:
    import Queue as queue  # Py2.7

from . import tk

try:
    # Python 3.4+
    _main_thread_ = threading.main_thread()
except AttributeError:
    # Python 3.3 support
    # we will assume that import is done on the main thread
    _main_thread_ = threading.current_thread()


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
                        try:
                            traceback.print_exc(file=sys.stderr)
                            print('retrying %r %i of %i' % (name, n+1, rcount),
                                  file=sys.stderr)
                        except:
                            # pythonw.exe sys.stderr is None
                            pass
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
        # GOAL: ensure init is performed on main thread
        # for Tcl/Tk to be bound to it.
        # WHY: matplotlib can create figure managers anywhere

        def _actual_init():
            tk._Tk_original_.__init__(self, *args, **kw)
            # patch the existing Tkapp object
            self.tk = _tk_dispatcher(self.tk)

        if threading.current_thread() is _main_thread_:
            # on main thread, proceed
            _actual_init()
        else:
            # using Tk?

            if len(args) >= 4:
                # hack, assuming arg order
                usetk = args[3]
            else:
                usetk = kw.get('useTk', True)

            if usetk:
                # we are using Tk, not on main thread
                if tk._default_root is None:
                    raise Exception(
                        'Tcl/Tk default root instance not initialized. '
                        'Try using `tkthread.tkinstall(ensure_root=True)`'
                        )

                main(sync=True)(_actual_init)
            else:
                # since we are not using Tk, let it initialize
                # on this thread
                _actual_init()


def tkinstall(ensure_root=False):
    """Replace tkinter's `Tk` class with a thread-enabled version"""
    import platform
    runtime = platform.python_implementation()
    if 'cpython' not in runtime.lower():
        raise RuntimeError('Requires CPython, not %s' % runtime)

    tk.__dict__.setdefault('_Tk_original_', tk.Tk)  # save the original version
    if tk.Tk is tk._Tk_original_:
        tk.Tk = _Tk


    if ensure_root:
        if tk._default_root:
            tk._default_root.update()  # in case of enqueued destruction

        if tk._default_root is None:
            w = tk.Tk()
            w.withdraw()
            return w
        else:
            return tk._default_root


def _tkuninstall():
    """Uninstall the thread-enabled version of Tk"""
    orig = tk.__dict__.get('_Tk_original_', None)
    if orig is None:
        return
    if tk.Tk is not orig:
        tk.Tk = orig


def current(widget=None, sync=True):
    """Decorator to run callable on the current thread.
        Useful for quickly changing with `tkthread.main`"""

    # sync is a no-op
    def wrapped(func):
        func()
        return func
    return wrapped


_ENSURE_COUNT = 10

def _ensure_after_idle(widget, func, tries=None):
    if tries is None:
        tries = _ENSURE_COUNT

    for n in range(tries):
        widget.willdispatch()
        try:
            result = widget.after_idle(func)
            break
        except RuntimeError as exc:
            # try again
            pass
    else:
        # unable to call after_idle
        raise RuntimeError('unable to call after_idle')
    return result


class _NoSyncHandler:
    '''
    _tkinter.c will dispatch non-mainthread calls to the mainthread,
    but will create a Tcl_Condition variable that blocks the calling thread.
    '''
    def __init__(self):
        self.q = queue.Queue()
        self.th = threading.Thread(
            target=self._dispatcher,
            name='tkthread.nosync',
            )
        self.th.daemon=True
        self.th.start()

    def _dispatcher(self):
        while True:
            func, args, kwargs = self.q.get()
            try:
                func(*args, **kwargs)
            except:
                # show the error
                try:
                    traceback.print_exc(file=sys.stderr)
                except:
                    # pythonw.exe sys.stderr is None
                    pass

    def call(self, func, *args, **kw):
        self.q.put((func, args, kw))


_nosync_handler = _NoSyncHandler()


def main(widget=None, sync=True):
    """Decorator to run callable (no arguments) on Tcl/Tk mainthread.

    example:

    @tkthread.main(sync=True)
    def _():
        ...  # this code runs on the main thread

    """
    def wrapped(func):
        w = widget
        if w is None:
            w = tk._default_root

        if threading.current_thread() is _main_thread_:
            if sync:
                func()
            else:
                w.after_idle(func)
        else:
            if sync:
                ev = threading.Event()
                def sync_wrapped(_func=func, _ev=ev):
                    try:
                        _func()
                    finally:
                        _ev.set()
                _ensure_after_idle(w, sync_wrapped)
                ev.wait()

            else:
                _nosync_handler.call(_ensure_after_idle, w, func)

        return func
    return wrapped


def _callsync(sync, func, args, kwargs):

    d = dict(
        outerr=None,   # result: output, error
        func=func,     # callable
        args=args,
        kwargs=kwargs,
        )

    def _handler(d=d):
        func = d['func']
        args = d['args']
        kwargs = d['kwargs']
        try:
            error = None
            result = func(*args, **kwargs)
        except BaseException as exc:
            result = None
            error = exc

        d['outerr'] = (result, error)

    main(sync=sync)(_handler)

    if sync:
        result, error = d['outerr']
        if error is not None:
            raise error
        else:
            return result


def call(func, *args, **kwargs):
    """Call the function on the main thread, wait for result."""
    return _callsync(True, func, args, kwargs)


def call_nosync(func, *args, **kwargs):
    """Enqueue the function for calling on the main thread, immediately return."""
    return _callsync(False, func, args, kwargs)


class called_on_main:
    """Decorator to cause function call to execute on the main thread.

    example:

    @tkthread.called_on_main
    def gui_code():
        ...

    gui_code()  # calling will automatically dispatch to main thread
    """
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kw):
        return call(self.func, *args, **kw)

    def __repr__(self):
        return '<called_on_main %r>' % self.func
