"""
Root Window
-----------

This demonstrates the RuntimeError typically encountered
when using Python threads with Tkinter. It also shows
two approaches to work around them:

    1. Use tkt() to wrap calls to tk widgets within a thread.
    2. Use tkt.install() to automatically wrap all calls.

The demo starts with a window with an "initializing..." title.
Two threads are started, which update the title.
The FAILURE update raises a RuntimeError in the terminal.
The SUCCESS update succeeds.

After two seconds, tkt.install() is called. The title
soon reads "NOT FAILURE", having be made from an unwrapped call.

After two more seconds, the program terminates.

"""
import __main__; print(__main__.__doc__)

import time
import threading

from tkthread import tk, TkThread

root = tk.Tk()
root.wm_title('initializing...')

tkt = TkThread(root)  # make the thread-safe callable

def run(func):
    threading.Thread(target=func).start()

run(lambda:     root.wm_title('FAILURE'))
run(lambda: tkt(root.wm_title,'SUCCESS'))

root.update()
time.sleep(2)  # _tkinter.c:WaitForMainloop fails

def retry_with_install():
    tkt.install()  # intercept .tkapp calls
    run(lambda: root.wm_title('NOT FAILURE'))

root.after(2000, retry_with_install)

root.after(4000, root.destroy)  # exit
root.mainloop()
