import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from rich.segment import Segment
from rich.style import Style
from textual.widgets import DataTable, Input, SelectionList

from console_ui import Details, FilePicker, Home, Journal, LogConsole, RevealFrame, Settings
from logic.settings import load_settings


class ConsoleTests(IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "sample.log"
        self.settings = Path(temp.name) / "settings.json"
        self.config = Path(temp.name) / "user.json"
        for target, value in [("logic.settings.settings_file", self.settings),
                              ("console_ui.NOTIFICATION_CONFIG", self.config)]:
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.send = Mock()
        self.app = LogConsole(self.send)

    def test_scramble_preserves_cells_styles_and_increasing_prefix(self):
        original = Segment("Главное  меню · 日誌", Style(bold=True))
        for progress, prefix in [(0, ""), (0.6, "Гла"), (1, "Главное")]:
            result, = RevealFrame(progress).apply([original], None)
            self.assertEqual(result.cell_length, original.cell_length)
            self.assertEqual(result.style, original.style)
            self.assertTrue(result.text.startswith(prefix))
            self.assertIn("  ", result.text)
            if progress < 1:
                self.assertTrue(set(result.text) & set(RevealFrame.SYMBOLS))
            else:
                self.assertEqual(result, original)

    async def test_navigation_during_reveal_and_centred_layout(self):
        async with self.app.run_test(size=(94, 28)) as pilot:
            self.assertIsNotNone(self.app.reveal_frame)
            await pilot.press("a", "escape", "m")
            screen = self.app.screen
            self.assertIsInstance(screen, FilePicker)
            self.assertTrue(screen.live)
            await pilot.pause(RevealFrame.DURATION + 0.12)
            self.assertIsNone(self.app.reveal_frame)
            self.assertIsNone(self.app.reveal_timer)
            for width, height in [(94, 28), (48, 18)]:
                await pilot.resize_terminal(width, height)
                for selector in [".section", ".title", "#path", "#open-file"]:
                    region = screen.query_one(selector).region
                    self.assertLessEqual(abs(region.x * 2 + region.width - width), 2)

    async def test_keyboard_analysis_filter_and_detail(self):
        self.path.write_text('[12:00:00] [Server/INFO]: Ready\n[12:00:01] [Server/ERROR]: Failed\n')
        async with self.app.run_test(size=(72, 22)) as pilot:
            await pilot.press("enter", "enter")
            self.assertIsInstance(self.app.screen, FilePicker)
            self.assertIn("Файл не найден", str(self.app.screen.query_one("#error").render()))
            self.app.screen.query_one(Input).value = str(self.path)
            await pilot.press("enter")
            await self.app.workers.wait_for_complete()
            journal = self.app.screen
            self.assertIsInstance(journal, Journal)
            table = journal.query_one(DataTable)
            self.assertEqual(table.row_count, 2)
            await pilot.press("down")
            self.assertEqual((self.app.theme, table.cursor_row), ("amber", 1))
            await pilot.press("f")
            self.assertEqual(table.row_count, 1)
            await pilot.press("enter")
            self.assertIsInstance(self.app.screen, Details)
            self.assertEqual(self.app.screen.entry["index"], 2)
            await pilot.press("escape", "escape")
            self.assertIsInstance(self.app.screen, Home)
            self.send.assert_not_called()

    async def test_settings_keyboard_and_save(self):
        async with self.app.run_test(size=(62, 20)) as pilot:
            await pilot.press("s")
            screen = self.app.screen
            self.assertIsInstance(screen, Settings)
            levels = screen.query_one(SelectionList)
            await pilot.press("space", "tab", "enter")
            self.assertEqual(load_settings()["DEBUG"], "DEBUG" in levels.selected)
            self.assertTrue(self.settings.exists())
            await pilot.press("escape")
            self.assertIsInstance(self.app.screen, Home)

    async def test_live_reader_stops_on_back_while_file_is_idle(self):
        self.path.touch()
        async with self.app.run_test() as pilot:
            await pilot.press("m")
            self.app.screen.query_one(Input).value = str(self.path)
            await pilot.press("enter")
            journal = self.app.screen
            for _ in range(30):
                with self.path.open("a") as log:
                    log.write("[12:00:00] [Server/INFO]: Tick\n")
                await pilot.pause(.05)
                if journal.total:
                    break
            self.assertGreater(journal.total, 0)
            await pilot.press("escape")
            await asyncio.wait_for(self.app.workers.wait_for_complete(), timeout=2)
            self.assertTrue(journal.stop.is_set())
            self.assertIsInstance(self.app.screen, Home)
