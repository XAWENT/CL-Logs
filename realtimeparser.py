import os
from threading import Event

from log_parser import parse_line


def follow(path, stop_event=None):
    if stop_event is None:
        stop_event = Event()
    if stop_event.is_set():
        return

    path = os.path.abspath(path)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)

        while not stop_event.is_set():
            line = f.readline()

            if line:
                yield line.rstrip("\n")
            else:
                stop_event.wait(0.1)


def start_mc_realtime(path, stop_event=None):
    for raw in follow(path, stop_event):

        if not raw.strip():
            continue

        parsed = parse_line(raw)
        yield parsed
