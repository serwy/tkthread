# tkthread

Easy multithreading with Tkinter on CPython 2.7/3.x and PyPy 2.7/3.x.

## Background

The Tcl/Tk language that comes with Python follows a different threading
model than Python itself which can raise obtuse errors when mixing Python
threads with Tkinter, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError: Call from another thread

Tcl can have many isolated interpreters, and each are tagged to the
its particular OS thread when created. Python's _tkinter module checks
if the calling Python thread is different than the Tcl/Tk thread, and if so,
[waits one second][WaitForMainloop] for the Tcl/Tk main loop to begin
dispatching. If there is a timeout, a RuntimeError is raised. On PyPy,
a [NotImplementedError][PyPyNotImplemented] is raised.

For non-Tk calls into Tcl, Python will raise an apartment RuntimeError
when calling a Tcl interpreter from a different thread.

A common approach to avoid these errors involves using `.after` to set up
[periodic polling][PollQueue] of a [message queue][PollRecipe] from
the Tcl/Tk main loop, which can slow the responsiveness of the GUI.

The approach used in `tkthread` is to use the Tcl/Tk `thread::send`
messaging to notify the Tcl/Tk main loop of a call for execution.
This interrupt-style architecture has lower latency and better
CPU utilization than periodic polling.

## Usage

The `tkthread` module provides the `TkThread` class, which can
synchronously interact with the main thread.

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

The `tkt` instance is callable, and will wait for the Tcl/Tk main loop
to execute and compute a result which is then passed back for
return in the calling thread. A non-synchronous version also exists that
does not block:

    tkt.nosync(root.wm_title, 'ALSO SUCCESS')

There is an optional `tkt.install()` method which intercepts Python-to-Tk
calls. This must be called on the default root, before the creation of child
widgets. If installed, then wrapping Tk widget calls in threaded code with
`tkt` is not necessary. There is, however, a slight performance penalty for
Tkinter widgets that operate only on the main thread because of the
thread-checking indirection.

The `root` Tcl/Tk interpreter must be the primary interpreter on the
main thread. If it is not, then you will receive a TclError of the form:

    _tkinter.TclError: invalid command name "140520536224520_call_from"

For example, creating several `Tk()` instances and then using TkThread
on those will cause this error.

A good practice is to create a root window and then call `root.withdraw()`
to keep the primary Tcl/Tk interpreter active. Future Toplevel windows
use `root` as the master.

## Install

    pip install tkthread

## License

Licensed under the Apache License, Version 2.0 (the "License")

## See Also

These libraries offer similar functionality, using periodic polling:
* https://github.com/RedFantom/mtTkinter
* https://github.com/abarnert/mttkinter
* https://pypi.org/project/threadsafe-tkinter

[PollQueue]: http://effbot.org/zone/tkinter-threads.htm
[PollRecipe]: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch09s07.html
[WaitForMainloop]: https://github.com/python/cpython/blob/38df97a03c5102e717a110ab69bff8e5c9ebfd08/Modules/_tkinter.c#L342
[PyPyNotImplemented]: https://bitbucket.org/pypy/pypy/src/d19ac6eec77b4e1859ab3dd8a5843989c4d4df99/lib_pypy/_tkinter/app.py?fileviewer=file-view-default#app.py-281
