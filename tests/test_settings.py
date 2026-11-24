import contextlib
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import main as cli
from logic.settings import default_dangers, load_settings, save_settings


class AnalysisSettingsTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.directory = Path(stack.enter_context(TemporaryDirectory()))
        self.path = self.directory / "settings.json"
        stack.enter_context(patch("logic.settings.settings_file", self.path))

    def test_failed_write_preserves_previous_settings_and_cleans_temporary_file(self):
        save_settings(default_dangers)
        previous = self.path.read_bytes()

        def interrupted_write(dangers, stream, **kwargs):
            stream.write("{")
            raise OSError("disk full")

        with patch("logic.settings.json.dump", side_effect=interrupted_write):
            with self.assertRaisesRegex(OSError, "disk full"):
                save_settings({"WARN": False})

        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_invalid_level_values_fall_back_to_defaults(self):
        self.path.write_text('{"WARN": "false", "INFO": true, "CUSTOM": true}', encoding="utf-8")
        self.assertEqual(load_settings(), {**default_dangers, "INFO": True, "CUSTOM": True})

    def test_classic_settings_failed_save_keeps_previous_levels_and_returns_to_menu(self):
        save_settings(default_dangers)
        output = io.StringIO()
        answers = ["1"] + ["0"] * len(default_dangers) + ["", "4"]
        with (contextlib.redirect_stdout(output),
              patch("sys.stdin.isatty", return_value=False),
              patch.object(cli, "menu", side_effect=["3", "3", "4"]),
              patch.object(cli, "save_settings", side_effect=PermissionError("settings.json")),
              patch("builtins.input", side_effect=answers)):
            cli.main()

        self.assertIn("Не удалось сохранить настройки анализа", output.getvalue())
        self.assertEqual(output.getvalue().count("WARN, ERROR, CRITICAL"), 2)
        self.assertEqual(load_settings(), default_dangers)
