import os
from threading import Event

from log_parser.parser_engine import _parse_redacted_line
from log_parser.redaction import LogRedactor


CHECKPOINT_SIZE = 64


def _matches_checkpoint(log, offset, checkpoint):
    # Seek from the end first to discard the buffered bytes from before a rewrite.
    log.seek(0, os.SEEK_END)
    log.seek(offset - len(checkpoint))
    matches = log.read(len(checkpoint)) == checkpoint
    log.seek(offset)
    return matches


def _open_replacement(path, descriptor_stat):
    try:
        if os.path.samestat(descriptor_stat, os.stat(path)):
            return None
        replacement = open(path, "rb")
    except FileNotFoundError:
        return None

    try:
        replacement_stat = os.fstat(replacement.fileno())
    except OSError:
        replacement.close()
        raise
    if os.path.samestat(descriptor_stat, replacement_stat):
        replacement.close()
        return None
    return replacement, replacement_stat


def follow(path, stop_event=None):
    """Yield redacted, complete lines written after monitoring starts."""
    if stop_event is None:
        stop_event = Event()
    if stop_event.is_set():
        return

    path = os.path.abspath(path)

    redactor = LogRedactor()
    log = open(path, "rb")
    try:
        log_stat = os.fstat(log.fileno())
        remaining = log.seek(0, os.SEEK_END)
        log.seek(0)
        pending = bytearray()
        checkpoint = b""
        # Establish redaction state for a sensitive block already open at startup.
        # A line that started before monitoring began stays out of the results.
        while remaining and not stop_event.is_set():
            chunk = log.readline(remaining)
            if not chunk:
                break
            remaining -= len(chunk)
            checkpoint = (checkpoint + chunk[-CHECKPOINT_SIZE:])[-CHECKPOINT_SIZE:]
            if chunk.endswith(b"\n"):
                redactor.redact(chunk.decode("utf-8", errors="replace").rstrip("\r\n"))
            else:
                pending.extend(chunk)
        skip_initial_line = bool(pending)

        while not stop_event.is_set():
            chunk = log.readline()
            pending.extend(chunk)
            if chunk:
                checkpoint = (checkpoint + chunk[-CHECKPOINT_SIZE:])[-CHECKPOINT_SIZE:]
            if not chunk.endswith(b"\n"):
                if stop_event.wait(0.1):
                    return

                offset = log.tell()
                descriptor_stat = os.fstat(log.fileno())
                # Finish reading the old descriptor before following the new file.
                replacement = (_open_replacement(path, descriptor_stat)
                               if descriptor_stat.st_size <= offset else None)
                if replacement is not None:
                    log.close()
                    log, descriptor_stat = replacement
                elif descriptor_stat.st_size < offset or (
                    checkpoint and log_stat.st_mtime_ns != descriptor_stat.st_mtime_ns
                    and not _matches_checkpoint(log, offset, checkpoint)
                ):
                    # A copy-truncated file can grow past the old offset between polls.
                    log.seek(0)
                else:
                    log_stat = descriptor_stat
                    continue

                # A discarded fragment may open a sensitive block but must not close one.
                if pending and not redactor.has_continuation():
                    redactor.redact(pending.decode("utf-8", errors="replace"))
                pending.clear()
                checkpoint = b""
                skip_initial_line = False
                log_stat = descriptor_stat
                continue

            line = pending.decode("utf-8", errors="replace").rstrip("\r\n")
            pending.clear()
            safe_line = redactor.redact(line)
            if skip_initial_line:
                skip_initial_line = False
            else:
                yield safe_line
    finally:
        log.close()


def start_mc_realtime(path, stop_event=None):
    for line in follow(path, stop_event):
        if line.strip():
            yield _parse_redacted_line(line)
