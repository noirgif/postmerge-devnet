import curses
import os
import subprocess
import threading
from typing import List


def is_display_available():
    try:
        os.environ['DISPLAY']
        return True
    except KeyError:
        return False

def execute_command(win, cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        win.addstr(line)
        win.refresh()

def create_window(xindex, yindex, title, total_x=2, total_y=2):
    max_y, max_x = curses.LINES, curses.COLS

    window_width = max_x // total_x
    window_height = max_y // total_y

    win = curses.newwin(window_height - 1, window_width - 1, yindex * window_height, xindex * window_width)
    win.scrollok(True)
    win.addstr(0, 0, f"{title}\n")
    win.refresh()
    return win

def run_in_curses(*node_cmd_lists: List[List[List[str]]]):
    def wrapper(stdscr):
        curses.curs_set(0)
        threads = []
        num_nodes = len(node_cmd_lists)

        for node, cmd_list in enumerate(node_cmd_lists):
            num_processes = len(cmd_list)
            for index, cmd in enumerate(cmd_list):
                win = create_window(index, node, " ".join(cmd), total_x=num_processes, total_y=num_nodes)
                t = threading.Thread(target=execute_command, args=(win, cmd))
                t.start()
                threads.append(t)            

        for t in threads:
            t.join()

        stdscr.getch()

    curses.wrapper(wrapper)
