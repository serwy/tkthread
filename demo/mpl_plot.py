"""
Matplotlib Demo

Show some simple plots using matplotlib and the TkAgg backend.
The program will quit after 5 seconds.

"""
import __main__; print(__main__.__doc__)


import tkthread
root = tkthread.tkinstall(ensure_root=True)


import matplotlib as mpl
mpl.rcParams['backend'] = 'TkAgg'

import matplotlib.pyplot as plt
import numpy as np


# set up a function that is invoked on the main thread
@tkthread.called_on_main
def main_call():
    x = np.linspace(0, 10, 1000)
    y = np.sin(x)
    ax2.plot(x, y, color='blue')
    ax2.set_title(repr(threading.current_thread()))


def thread_call():
    print('starting a plot from: ', threading.current_thread())
    global fig, ax1, ax2
    plt.ion()
    x = np.linspace(0, 10, 1000)
    y = np.sin(x)
    fig = plt.figure(2)
    ax1, ax2 = fig.subplots(2, 1)
    ax1.plot(x, y, color='red')
    ax1.set_title(repr(threading.current_thread()))
    main_call()
    print('finished')

import threading
threading.Thread(target=thread_call, daemon=True).start()

print('starting main loop, quit in 5 seconds')
root.after(5000, root.quit)
root.mainloop()
