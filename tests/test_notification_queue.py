from threading import Event
from time import monotonic, sleep
import unittest

from logic.notification_queue import NotificationQueue


class DeliveryTests(unittest.TestCase):
    def test_slow_recipient_does_not_block_producer_and_overflow_is_counted(self):
        entered, release = Event(), Event()
        calls = []

        def send(level, message, source, timestamp, recipient):
            calls.append((message, timestamp, recipient))
            entered.set()
            release.wait(5)
            return message == "first"

        queue = NotificationQueue(send, capacity=1)
        self.addCleanup(queue.close)
        self.addCleanup(release.set)
        entry = {"level": "ERROR", "message": "first", "date": "N", "time": "10:11:12", "source": "test"}
        queue.submit(entry, "receiverA")
        self.assertTrue(entered.wait(2))
        queue.submit(dict(entry, message="second"), "receiverB")
        queue.submit(dict(entry, message="third"), "receiverB")
        self.assertEqual(queue.counts(), (0, 0, 1, 2))
        release.set()
        deadline = monotonic() + 2
        while queue.counts() != (1, 1, 1, 0) and monotonic() < deadline:
            sleep(0.01)
        self.assertEqual(queue.counts(), (1, 1, 1, 0))
        self.assertEqual(calls, [("first", "10:11:12", "receiverA"), ("second", "10:11:12", "receiverB")])
