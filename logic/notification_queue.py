"""Bounded background delivery for the interactive log viewers."""

from collections import deque
from threading import Condition, Thread


class NotificationQueue:
    def __init__(self, sender, capacity=128):
        self._sender = sender
        self._capacity = capacity
        self._condition = Condition()
        self._pending = deque()
        self._worker = None
        self._closed = False
        self._submitted = self._sent = self._failed = self._skipped = 0

    def submit(self, entry, recipient):
        timestamp = " ".join(entry[key] for key in ("date", "time") if entry[key] != "N")
        with self._condition:
            self._submitted += 1
            if self._closed or len(self._pending) >= self._capacity:
                self._skipped += 1
                return
            self._pending.append((entry["level"], entry["message"], entry["source"], timestamp, recipient))
            if self._worker is None:
                self._worker = Thread(target=self._deliver, daemon=True)
                try:
                    self._worker.start()
                except RuntimeError:
                    self._worker = None
                    self._pending.pop()
                    self._failed += 1
                    return
            self._condition.notify()

    def _deliver(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._pending)
                if self._closed:
                    return
                payload = self._pending.popleft()
            try:
                delivered = self._sender(*payload)
            except Exception:
                delivered = False
            with self._condition:
                if delivered:
                    self._sent += 1
                else:
                    self._failed += 1

    def counts(self):
        with self._condition:
            pending = self._submitted - self._sent - self._failed - self._skipped
            return self._sent, self._failed, self._skipped, pending

    def discard_pending(self):
        with self._condition:
            self._skipped += len(self._pending)
            self._pending.clear()

    def close(self):
        with self._condition:
            self._closed = True
            self.discard_pending()
            self._condition.notify()
