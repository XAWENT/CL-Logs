import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gui import LogAnalyzerApp
from logic.realtime_logic import iterate_realtime


class ObservedStopEvent(threading.Event):
    def __init__(self):
        super().__init__()
        self.waiting = threading.Event()

    def wait(self, timeout=None):
        self.waiting.set()
        return super().wait(timeout)


class RealtimeTests(unittest.TestCase):
    def test_monitor_exits_at_eof_without_another_line(self):
        stop_event = ObservedStopEvent()
        results = queue.Queue()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            path.write_text("existing log line\n", encoding="utf-8")

            def monitor():
                results.put(list(iterate_realtime(path, {}, stop_event)))

            worker = threading.Thread(target=monitor, daemon=True)
            worker.start()
            try:
                self.assertTrue(stop_event.waiting.wait(2))
            finally:
                stop_event.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results.get_nowait(), [])

    def test_cli_caller_can_still_read_appended_lines_without_stop_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            path.write_text("existing log line\n", encoding="utf-8")
            entry_text = '{"level":"ERROR","message":"appended record"}'
            append_event = Mock()
            append_event.is_set.return_value = False

            def append_line(timeout):
                with path.open("a", encoding="utf-8") as log_file:
                    log_file.write(entry_text + "\n")

            append_event.wait.side_effect = append_line
            with patch("realtimeparser.Event", return_value=append_event):
                entries = iterate_realtime(path, {"ERROR": True})
                try:
                    entry = next(entries)
                finally:
                    entries.close()

            self.assertEqual(entry["index"], 1)
            self.assertEqual(entry["raw"], entry_text)
            self.assertTrue(entry["is_danger"])


class GuiOperationTests(unittest.TestCase):
    def setUp(self):
        self.app = app = LogAnalyzerApp.__new__(LogAnalyzerApp)
        app.root = Mock()
        app.log_queue = queue.Queue()
        app._active_operation = None
        app._queue_callback = None
        app._closing = False
        app.realtime_running = False
        app.current_log_path = "first.log"
        app.dangers = {"ERROR": True}
        app.realtime_btn = Mock()
        app.analyze_btn = Mock()
        app.stop_btn = Mock()
        app.status_var = Mock()
        app.clear_entries = Mock()
        app.add_entry = Mock()
        app.update_stats_display = Mock()

    def assert_idle(self):
        self.assertIsNone(self.app._active_operation)
        self.assertFalse(self.app.realtime_running)
        self.app.realtime_btn.config.assert_called_with(state="normal")
        self.app.analyze_btn.config.assert_called_with(state="normal")
        self.app.stop_btn.config.assert_called_with(state="disabled")

    @patch("gui.messagebox.showerror")
    @patch("gui.threading.Thread")
    def test_restart_discards_previous_entries_and_worker_errors(self, thread, showerror):
        self.app.start_realtime()
        old_operation, path, dangers = thread.call_args.kwargs["args"]
        self.app.stop_realtime()
        self.assertTrue(old_operation.is_set())
        self.app.current_log_path = "second.log"
        self.app.dangers["ERROR"] = False
        self.app.start_realtime()
        new_operation = self.app._active_operation

        self.assertIsNot(old_operation, new_operation)
        self.assertEqual((path, dangers), ("first.log", {"ERROR": True}))
        self.app.log_queue.put((old_operation, "entry", "stale entry"))
        self.app.log_queue.put((old_operation, "error", "stale failure"))
        self.app.log_queue.put((old_operation, "realtime_finished", None))
        self.app.log_queue.put((new_operation, "entry", "current entry"))
        self.app.process_queue()

        self.app.add_entry.assert_called_once_with("current entry")
        showerror.assert_not_called()
        self.assertTrue(self.app.realtime_running)
        self.assertIs(self.app._active_operation, new_operation)

    @patch("gui.threading.Thread")
    def test_monitor_completion_restores_buttons(self, thread):
        self.app.start_realtime()
        worker = thread.call_args.kwargs
        with patch("gui.iterate_realtime", return_value=iter(["entry"])):
            worker["target"](*worker["args"])

        self.app.add_entry.assert_not_called()
        self.app.process_queue()
        self.app.add_entry.assert_called_once_with("entry")
        self.assert_idle()
        self.app.status_var.set.assert_called_with("Мониторинг завершен")

    @patch("gui.messagebox.showerror")
    @patch("gui.threading.Thread")
    def test_worker_failures_are_handled_in_the_queue(self, thread, showerror):
        for start, parser in [
            (self.app.start_realtime, "gui.iterate_realtime"),
            (self.app.analyze_log, "gui.analyze_log"),
        ]:
            with self.subTest(parser=parser):
                start()
                worker = thread.call_args.kwargs
                showerror.reset_mock()
                with patch(parser, side_effect=FileNotFoundError("missing.log")):
                    worker["target"](*worker["args"])

                showerror.assert_not_called()
                self.app.analyze_btn.config.assert_called_with(state="disabled")
                self.app.process_queue()
                self.assert_idle()
                showerror.assert_called_once_with("Ошибка", "missing.log")
                self.app.status_var.set.assert_called_with("Ошибка: missing.log")

    @patch("gui.threading.Thread")
    def test_successful_analysis_restores_buttons_and_publishes_stats(self, thread):
        self.app.analyze_log()
        self.app.start_realtime()
        thread.assert_called_once()
        worker = thread.call_args.kwargs
        with patch("gui.analyze_log", return_value=(["entry"], [1])):
            worker["target"](*worker["args"])

        self.app.add_entry.assert_not_called()
        self.app.update_stats_display.assert_not_called()
        self.app.process_queue()
        self.app.add_entry.assert_called_once_with("entry")
        self.app.update_stats_display.assert_called_once_with({
            "total": 1,
            "danger": 1,
            "danger_lines": [1],
        })
        self.assert_idle()

    @patch("gui.threading.Thread")
    def test_close_signals_worker_and_cancels_queue_callback(self, thread):
        self.app.start_realtime()
        operation = self.app._active_operation
        self.app.process_queue()
        callback = self.app._queue_callback
        self.app.close()

        self.assertTrue(operation.is_set())
        self.app.root.after_cancel.assert_called_once_with(callback)
        self.app.root.destroy.assert_called_once()
        self.app.process_queue()
        self.app.root.after.assert_called_once()


if __name__ == "__main__":
    unittest.main()
