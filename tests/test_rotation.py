import tempfile
import threading
import unittest
from pathlib import Path

from realtimeparser import follow


class IdleSteps(threading.Event):
    def __init__(self, *steps):
        super().__init__()
        self.steps = iter(steps)

    def wait(self, timeout=None):
        next(self.steps, self.set)()
        return self.is_set()


class RotationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "service.log"
        self.rotated = self.path.with_suffix(".log.1")

    def append(self, path, text):
        with path.open("a", encoding="utf-8") as log:
            log.write(text)

    def test_drains_renamed_file_and_resumes_when_path_reappears(self):
        self.path.write_text("old file history\n", encoding="utf-8")

        def rename():
            self.path.rename(self.rotated)
            self.append(self.rotated, "last line in the old file\n")

        def delayed_writer():
            self.assertFalse(self.path.exists())
            self.append(self.rotated, "another line in the old file\nold fragment")

        def recreate():
            self.path.write_text("first line in new file\nnew fr", encoding="utf-8")

        stop = IdleSteps(rename, delayed_writer, recreate,
                         lambda: self.append(self.path, "agment completed\n"))

        self.assertEqual(list(follow(self.path, stop)), [
            "last line in the old file",
            "another line in the old file",
            "first line in new file",
            "new fragment completed",
        ])
        self.assertTrue(stop.is_set())

    def test_copytruncate_reads_rewritten_file_from_start(self):
        for new_data in ("new line\n", "new line\n" * 80):
            with self.subTest(new_size=len(new_data)):
                self.path.write_text("older line\n" * 20 + "initial fragment", encoding="utf-8")

                def truncate_and_write():
                    self.path.write_text(new_data, encoding="utf-8")

                stop = IdleSteps(truncate_and_write)
                self.assertEqual(list(follow(self.path, stop)), new_data.splitlines())

    def test_redacts_open_block_across_rotation_and_truncation(self):
        for rotate in (False, True):
            with self.subTest(rotate=rotate):
                self.path.write_text("-----BEGIN PRIVATE KEY-----\n" * 4, encoding="utf-8")

                def rewrite():
                    if rotate:
                        self.path.replace(self.rotated)
                    self.path.write_text("opaque-key-body\n", encoding="utf-8")

                def finish_key():
                    self.append(self.path, "-----END PRIVATE KEY-----\nregular line\n")

                stop = IdleSteps(
                    lambda: self.append(self.path, "-----END PRIVATE KEY-----"),
                    rewrite,
                    finish_key,
                )
                self.assertEqual(list(follow(self.path, stop)), ["******", "******", "regular line"])

    def test_discarded_partial_opening_marker_masks_following_lines(self):
        self.path.write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")

        def replace():
            self.path.replace(self.rotated)
            self.path.write_text(
                "opaque-key-body\n-----END PRIVATE KEY-----\nregular line\n",
                encoding="utf-8",
            )

        self.assertEqual(list(follow(self.path, IdleSteps(replace))),
                         ["******", "******", "regular line"])

    def test_stops_while_waiting_for_missing_path(self):
        self.path.touch()
        stop = IdleSteps(self.path.unlink)
        self.assertEqual(list(follow(self.path, stop)), [])
        self.assertTrue(stop.is_set())
