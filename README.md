# tkthread

Calling the Tcl/Tk event loop with Python multi-threading.
Works with CPython 2.7/3.x and PyPy 2.7/3.x.


## Background

The Tcl/Tk language is shipped along with Python, and follows a
different threading model than Python which can then
raise obtuse errors when mixing Python threads with Tk, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError('Call from another thread',)

Tcl can have many isolated interpreters running, and are
tagged to a particular system thread. Calling a Tcl interpreter
from a different thread raises the apartment error.
Python's `tkinter` library assumes that the Tcl/Tk GUI event loop
runs on the main thread.

A common approach to avoid these errors involves setting up 
periodic polling of a message queue from the Tk main thread, which
can [slow the responsiveness of the GUI.][1] 

The approach used in `tkthread` is to use the Tcl/Tk inter-interpreter 
communication to notify the main Tcl/Tk interpreter of a call.

## Usage

The `tkthread` module provides `tkt`, a callable instance of
`TkThread` which synchronously interacts with the main thread.
A new `Tk` root window is created and then withdrawn, which keeps
that Tcl/Tk event loop active. Future top-level windows should
use `tkt.root` as the master.

    from tkthread import tkt

    # [code for GUI and threading]

    text.insert('end-1c', 'some text')       # fails
    tkt(text.insert, 'end-1c', 'some text')  # succeeds

The `tkt()` object is callable, and will wait for the main thread
to execute and compute a result, which is then passed back for
return from `tkt()`. A non-synchronous version also exists that
does not block:

    tkt.nosync(text.insert, 'end-1c', 'some text')

## Install

    pip install tkthread

## Other

If you receive the following error:

    RuntimeError: Tcl is threaded but _tkinter is not

then your binaries are built with the wrong configuration flags.

## References

[1]: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch09s07.html


