"""
Progress Demo
-------------

This program displays a box with two fields. There are
two threads running a computation that interacts with Tk
and also writes to STDOUT.
    Thread   Sync - waits for the main thread to process
    Thread NoSync - enqueues the call to main and continues

After a few seconds, the main thread is blocked, and
the GUI updates stop. Thread Sync is blocked as well,
but Thread NoSync continues, as shown by the STDOUT output.

When the main thread unblocks, the No Sync thread is ahead
of the Sync thread.

"""
import __main__; print(__main__.__doc__)

import time
import threading

from tkthread import tk, TkThread

root = tk.Tk()
root.wm_title('Progress Demo')
tkt = TkThread(root)  # make the thread-safe callable

ent_sync = tk.Entry(root)
ent_sync.pack()

ent_nosync = tk.Entry(root)
ent_nosync.pack()

def run(func, name=None):
    threading.Thread(target=func, name=name).start()

def long_computation(entry, tkt_wrap):
    th = threading.current_thread()

    for i in range(101):
        txt = 'Progress: %02i' % i
        print(th, txt)  # send to terminal

        tkt_wrap(entry.delete, '0', 'end')
        tkt_wrap(entry.insert, '0', txt)
        time.sleep(0.125)

run(lambda: long_computation(ent_sync, tkt), name='  Sync')
run(lambda: long_computation(ent_nosync, tkt.nosync), name='NoSync')

def pause():
    # block the main thread from executing
    ent_sync.insert('end', ' block main thread')
    ent_sync.update()
    time.sleep(5)

root.after(2500, pause)

root.mainloop()
