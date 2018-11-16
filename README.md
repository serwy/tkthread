# tkthread

Easy multithreading with Tkinter on CPython 2.7/3.x and PyPy 2.7/3.x.

## Background

The Tcl/Tk language is shipped with Python, and follows a
different threading model than Python itself which can
raise obtuse errors when mixing Python threads with Tk, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError: Call from another thread

Tcl can have many isolated interpreters running, and are
tagged to a particular OS thread. Calling a Tcl interpreter
from a different thread raises an apartment error.

The _tkinter module detect if a Python thread is different
from the Tcl interpreter thread, and then waits one second
to acquire a lock on the main thread. If there is a time-out,
a RuntimeError is raised.

A common approach to avoid these errors involves setting up 
periodic polling of a message queue from the Tk main thread, which
can [slow the responsiveness of the GUI.][1] 

The approach used in `tkthread` is to use the Tcl/Tk `thread::send`
inter-interpreter messaging to notify the main Tcl/Tk interpreter 
of a call for execution.

## Usage

The `tkthread` module provides the `TkThread` class, which can
synchronously interact with the main thread.

    from tkthread import tk, TkThread

    root = tk.Tk()        # create the root window
    tkt = TkThread(root)  # make the thread-safe callable

    import threading, time
    def run(func):
        threading.Thread(target=func).start()

    run(lambda: root.wm_title('FAILURE'))
    run(lambda: tkt(root.wm_title, 'SUCCESS'))

    root.update()
    time.sleep(2)  # _tkinter.c:WaitForMainloop fails
    root.mainloop()

The `tkt()` instance is callable, and will wait for the main thread
to execute and compute a result, which is then passed back for
return from `tkt()`. A non-synchronous version also exists that
does not block:

    tkt.nosync(root.wm_title, 'ALSO SUCCESS')

There is an optional `tkt.install()` method which intercepts 
Python-to-Tk calls. This must be called on the default root, 
before the creation of child widgets. There is a slight performance
penalty for Tkinter widgets that operate only on the main thread.

The `root` Tcl/Tk interpreter must be the primary interpreter on the
main thread. If it is not, then you will receive a TclError of the form:

    _tkinter.TclError: invalid command name "140520536224520_call_from"

Creating several `Tk()` instances and then using TkThread on those will cause this error.

A good practice is to create a root window and then call `root.withdraw()`
to keep the primary Tcl/Tk interpreter active. Future Toplevel windows
use `root` as the master.

## Install

    pip install tkthread

## License

Licensed under the Apache License, Version 2.0 (the "License")


[1]: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch09s07.html


