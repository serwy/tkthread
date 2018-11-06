# tkthread

Calling the Tcl/Tk event loop with Python multi-threading.
Works with CPython 2.7/3.x and PyPy 2.7/3.x.


## Background

The Tcl/Tk language is shipped with Python, and follows a
different threading model than Python itself which can
raise obtuse error when mixing Python threads with Tk, such as:

    RuntimeError: main thread is not in main loop
    RuntimeError: Calling Tcl from different apartment
    NotImplementedError('Call from another thread',)

Tcl can have many isolated interpreters running, and are
tagged to a particular system thread. Calling a Tcl interpreter
from a different thread raises the apartment error.

## Usage

The `tkthread` module provides `tkt`, a callable instance of
`TkThread` which synchronously interacts with the main thread.

    from tkthread import tkt

    # [code for GUI and threading]

    text.insert('end-1c', 'some text')       # fails
    tkt(text.insert, 'end-1c', 'some text')  # succeeds


## Other

If you receive the following error:

    RuntimeError: Tcl is threaded but _tkinter is not

then your binaries are built with the wrong configuration flags.
