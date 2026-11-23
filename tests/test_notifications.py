import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import gui
import main as cli
from logic.notifications import NOTIFICATION_URL_ENV, load_config


class NotificationTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("sys.stdin.isatty", return_value=False))
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        self.config_path = Path(directory) / "user_config.json"
        self.app = gui.LogAnalyzerApp.__new__(gui.LogAnalyzerApp)
        self.app.user_config_path = self.config_path
        stack.enter_context(patch.object(cli, "NOTIFICATION_CONFIG", self.config_path))
        self.env = stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.get = stack.enter_context(patch("requests.get"))
        self.post = stack.enter_context(patch("requests.post"))
        self.showinfo = stack.enter_context(patch.object(gui.messagebox, "showinfo"))
        self.askyesno = stack.enter_context(patch.object(gui.messagebox, "askyesno"))
        self.askstring = stack.enter_context(patch.object(gui.simpledialog, "askstring"))
        self.output = io.StringIO()
        stack.enter_context(contextlib.redirect_stdout(self.output))

    def save_legacy_hash(self):
        self.config_path.write_text('{"user_hash": "LOCAL123"}', encoding="utf-8")
        self.app.load_user_config()

    def test_missing_or_invalid_url_blocks_setup_and_sending(self):
        self.save_legacy_hash()
        original_config = self.config_path.read_bytes()

        with patch("builtins.input") as user_input:
            for url in (None, "", "   ", "notifications.example", "ftp://notifications.example",
                        "https://", "https://notifications.example:bad"):
                with self.subTest(url=url):
                    if url is None:
                        self.env.pop(NOTIFICATION_URL_ENV, None)
                    else:
                        self.env[NOTIFICATION_URL_ENV] = url
                    self.assertEqual(cli.check_notifications_status(), ("LOCAL123", False))
                    self.assertFalse(self.app.can_send_notifications())
                    self.assertEqual(cli.setup_notifications(), ("LOCAL123", False))
                    self.assertFalse(self.app.setup_notifications_gui())
                    self.assertFalse(cli.send_notification("ERROR", "test", "sample", user_hash="LOCAL123"))
                    self.assertFalse(self.app.send_notification("ERROR", "test", "sample"))
            user_input.assert_not_called()

        self.assertIn(NOTIFICATION_URL_ENV, self.output.getvalue())
        self.assertIn(NOTIFICATION_URL_ENV, self.showinfo.call_args.args[1])
        self.askyesno.assert_not_called()
        self.askstring.assert_not_called()
        self.get.assert_not_called()
        self.post.assert_not_called()
        self.assertEqual(self.config_path.read_bytes(), original_config)

    def test_fresh_install_has_no_recipient_even_with_server(self):
        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.app.load_user_config()

        self.assertEqual(cli.check_notifications_status(), (None, False))
        self.assertFalse(self.app.can_send_notifications())
        self.assertFalse(cli.send_notification("ERROR", "test", "sample"))
        self.assertFalse(self.app.send_notification("ERROR", "test", "sample"))
        self.post.assert_not_called()

    def test_cli_disable_persists_and_gui_can_reenable_same_hash(self):
        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.save_legacy_hash()
        self.assertEqual(cli.check_notifications_status(), ("LOCAL123", True))
        self.assertTrue(self.app.can_send_notifications())

        with (patch.object(cli, "load_settings", return_value={}),
              patch.object(cli, "menu", side_effect=["3", "4"]),
              patch("builtins.input", side_effect=["3", "2", ""])):
            cli.main()
        self.assertEqual(load_config(self.config_path), ("LOCAL123", False))
        self.assertEqual(cli.check_notifications_status(), ("LOCAL123", False))

        self.app.load_user_config()
        self.assertFalse(self.app.can_send_notifications())
        self.assertFalse(self.app.send_notification("ERROR", "test", "sample"))
        self.askyesno.return_value = True
        self.assertTrue(self.app.setup_notifications_gui())
        self.assertTrue(self.app.can_send_notifications())
        self.assertEqual(cli.check_notifications_status(), ("LOCAL123", True))
        self.get.assert_not_called()
        self.post.assert_not_called()

    def test_canceling_hash_change_preserves_configuration(self):
        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.save_legacy_hash()
        original_config = self.config_path.read_bytes()
        self.askstring.return_value = None

        with patch("builtins.input", return_value=""):
            self.assertEqual(cli.setup_notifications(change_hash=True), ("LOCAL123", True))
        self.assertFalse(self.app.setup_notifications_gui(change_hash=True))
        self.assertTrue(self.app.can_send_notifications())
        self.assertEqual(self.config_path.read_bytes(), original_config)
        self.get.assert_not_called()
        self.post.assert_not_called()

    def test_cli_persists_disable_when_server_is_unconfigured(self):
        self.save_legacy_hash()
        with (patch.object(cli, "load_settings", return_value={}),
              patch.object(cli, "menu", side_effect=["3", "4"]),
              patch("builtins.input", side_effect=["3", "2", ""])):
            cli.main()

        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.assertEqual(cli.check_notifications_status(), ("LOCAL123", False))
        self.get.assert_not_called()
        self.post.assert_not_called()

    def test_gui_reports_email_delivery_failure(self):
        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.save_legacy_hash()
        self.post.side_effect = [Mock(status_code=200), Mock(status_code=503)]
        self.assertFalse(self.app.send_notification("ERROR", "test", "sample"))

    def test_cli_and_gui_mask_sensitive_notification_fields_before_delivery(self):
        self.env[NOTIFICATION_URL_ENV] = "https://notifications.example"
        self.save_legacy_hash()
        self.post.return_value = Mock(status_code=200)
        args = ("ERROR", "api_key=request-secret", "operator@example.test", "token=timestamp-secret")

        self.assertTrue(cli.send_notification(*args, user_hash="LOCAL123"))
        self.assertTrue(self.app.send_notification(*args))

        payloads = [call.kwargs["json"] for call in self.post.call_args_list]
        self.assertEqual(len(payloads), 4)
        self.assertEqual(payloads[:2], payloads[2:])
        for payload in payloads:
            self.assertIn("api_key=******", payload["message"])
            self.assertEqual(payload["user_hash"], "LOCAL123")
        for secret in ("request-secret", "operator@example.test", "timestamp-secret"):
            self.assertNotIn(secret, repr(payloads))
        self.assertIn("token=******", payloads[1]["subject"])

    def test_setup_and_sending_use_configured_url(self):
        self.env[NOTIFICATION_URL_ENV] = " https://notifications.example/api/ "
        self.get.return_value = Mock(status_code=200)
        self.post.return_value = Mock(status_code=200)
        self.post.return_value.json.return_value = {"user": {"first_name": "Test"}}
        self.app.load_user_config()

        with patch("builtins.input", return_value="cli12345"):
            self.assertEqual(cli.setup_notifications(), ("CLI12345", True))
        self.askstring.return_value = "gui12345"
        self.assertTrue(self.app.setup_notifications_gui(change_hash=True))
        self.assertEqual(cli.check_notifications_status(), ("GUI12345", True))

        self.assertTrue(cli.send_notification("ERROR", "test", "sample", user_hash="CLI12345"))
        self.assertTrue(self.app.send_notification("ERROR", "test", "sample"))
        base_url = "https://notifications.example/api"
        self.assertEqual([call.args[0] for call in self.get.call_args_list], [f"{base_url}/"] * 2)
        posts = [(call.args[0], call.kwargs["json"]["user_hash"]) for call in self.post.call_args_list]
        self.assertEqual(posts, [
            (f"{base_url}/send", "CLI12345"),
            (f"{base_url}/send", "GUI12345"),
            (f"{base_url}/send", "CLI12345"),
            (f"{base_url}/send_email", "CLI12345"),
            (f"{base_url}/send", "GUI12345"),
            (f"{base_url}/send_email", "GUI12345"),
        ])


if __name__ == "__main__":
    unittest.main()
