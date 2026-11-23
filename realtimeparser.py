import os
from threading import Event

from log_parser.parser_engine import _parse_redacted_line
from log_parser.redaction import LogRedactor


def follow(path, stop_event=None):
    """Yield redacted, complete lines appended after monitoring starts."""
    if stop_event is None:
        stop_event = Event()
    if stop_event.is_set():
        return

    path = os.path.abspath(path)

    redactor = LogRedactor()
    with open(path, "rb") as f:
        remaining = f.seek(0, os.SEEK_END)
        f.seek(0)
        pending = bytearray()
        # Establish redaction state for a sensitive block already open at startup.
        # A line that started before monitoring began stays out of the results.
        while remaining and not stop_event.is_set():
            chunk = f.readline(remaining)
            if not chunk:
                break
            remaining -= len(chunk)
            if chunk.endswith(b"\n"):
                redactor.redact(chunk.decode("utf-8", errors="replace").rstrip("\r\n"))
            else:
                pending.extend(chunk)
        skip_initial_line = bool(pending)

        while not stop_event.is_set():
            chunk = f.readline()
            pending.extend(chunk)
            if not chunk.endswith(b"\n"):
                stop_event.wait(0.1)
                continue

            line = pending.decode("utf-8", errors="replace").rstrip("\r\n")
            pending.clear()
            safe_line = redactor.redact(line)
            if skip_initial_line:
                skip_initial_line = False
            else:
                yield safe_line


def start_mc_realtime(path, stop_event=None):
    for line in follow(path, stop_event):
        if line.strip():
            yield _parse_redacted_line(line)
