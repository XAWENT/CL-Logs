import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from log_parser import parse_file, parse_line
from log_parser import parser_engine
from log_parser.redaction import mask_sensitive
from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime


class RedactionTests(unittest.TestCase):
    def test_nested_json_is_redacted_before_parsing_and_serializing_fields(self):
        entry = parse_line(
            r'  {"level":"WARNING","source":"203.0.113.42","message":{"p\u0061ssword":"quoted-secret",'
            r'"payload":"phone=+1 202 555 0149","records":[{"apiKey":123456789,"state":"retrying"}]},'
            r'"ids":["trace-id",{"access_token":"nested-secret","user_id":79409}]}  '
        )
        self.assertEqual((entry["format"], entry["level"], entry["source"]), ("json", "WARN", "******"))
        self.assertEqual(json.loads(entry["message"])["records"], [{"apiKey": "******", "state": "retrying"}])
        self.assertEqual(entry["ids"], ["trace-id", {"access_token": "******", "user_id": "******"}])
        self.assertEqual(json.loads(entry["raw"])["message"]["password"], "******")
        for secret in ("203.0.113.42", "quoted-secret", "202 555 0149", "nested-secret", "79409", "123456789"):
            self.assertNotIn(secret, repr(entry))

    def test_free_text_masks_credentials_without_removing_request_context(self):
        entry = parse_line(
            "INFO user=privacy-user db_password='two words' email=account@example.test "
            "POST https://dbuser:dbpass@db.example.test/job?%61ccess_token=query-secret&code=oauth-secret&attempt=2 "
            "via [2001:db8::354]:8080 card 4111 1111 1111 1111 Authorization: Digest response=opaque-hash"
        )
        for secret in ("privacy-user", "two words", "account@example.test", "dbuser", "dbpass",
                       "query-secret", "oauth-secret", "2001:db8::354", "4111", "opaque-hash"):
            self.assertNotIn(secret, repr(entry))
        self.assertEqual(entry["level"], "INFO")
        self.assertIn("https://******@db.example.test/job?%61ccess_token=******&code=******&attempt=2", entry["message"])
        self.assertIn("[******]:8080", entry["message"])

    def test_duplicate_json_fields_cannot_hide_an_earlier_secret(self):
        entry = parse_line('{"msg":"token=discarded-secret","msg":"safe","message":"ready"}')
        self.assertEqual(entry["message"], "ready")
        self.assertNotIn("discarded-secret", entry["raw"])

    def test_parser_error_does_not_echo_exception_or_input_credentials(self):
        parser = SimpleNamespace(match=lambda line: True, parse=Mock(side_effect=ValueError("private diagnostic")))
        with patch.object(parser_engine, "_load_parsers", return_value=[parser]):
            entry = parse_line("ERROR token=secret-input")

        parser.parse.assert_called_once_with("ERROR token=******")
        self.assertEqual(entry["format"], "parser_error")
        self.assertEqual(entry["message"], "Parser failed: SimpleNamespace")
        self.assertNotIn("secret-input", repr(entry))

    def test_access_log_keeps_status_and_masks_positional_user_and_network_address(self):
        entry = parse_line(
            '2001:db8::42 remote-ident private-user [13/Feb/2025:11:02:03 +0000] '
            '"GET /report?api_key=secret-link&view=summary HTTP/1.1" 503 9'
        )
        self.assertEqual(entry["format"], "nginx_apache")
        self.assertEqual(entry["source"], "******")
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["message"], "GET /report?api_key=******&view=summary 503")
        self.assertTrue(entry["raw"].startswith("****** ****** ****** "))

    def test_generic_timestamp_keeps_fractional_seconds(self):
        entry = parse_line("2025-11-24 12:34:56.123456 worker ready")
        self.assertEqual((entry["date"], entry["time"], entry["message"]),
                         ("2025-11-24", "12:34:56.123456", "worker ready"))

    def test_parser_routing_and_messages_survive_masked_metadata(self):
        for line, format_name in (
            ("2025-01-15 10:30:45,123 - 203.0.113.42 - ERROR - Request failed", "python_logging"),
            ("[Mon Jan 15 10:30:45 2024] [error] [client 203.0.113.42:443] Request failed", "apache_error"),
            ("2024/01/15 10:30:45 [error] 123#456: 203.0.113.42:443 - Request failed", "nginx_error"),
        ):
            with self.subTest(format=format_name):
                entry = parse_line(line)
                self.assertEqual(entry["format"], format_name)
                self.assertEqual(entry["message"], "Request failed")
                self.assertNotIn("203.0.113.42", repr(entry))

    def test_file_analysis_handles_multiline_secrets_and_preserves_line_numbers(self):
        contents = (
            "WARN private_key=-----BEGIN PRIVATE KEY-----\nopaque-key-material\n-----END PRIVATE KEY-----\n"
            '  "credentials": {\n    "arbitrary-name": "opaque-credential"\n  },\n'
            "Authorization: Bearer\n  opaque-folded-header\n"
            "ERROR failed password=opaque-password\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            path.write_text(contents, encoding="utf-8")
            parsed = list(parse_file(path))
            entries, danger_lines = analyze_log(path, {"ERROR": True})
            self.assertEqual(path.read_text(encoding="utf-8"), contents)

        self.assertEqual(len(parsed), len(entries))
        self.assertEqual(danger_lines, [9])
        self.assertEqual(entries[-1]["raw"], "ERROR failed password=******")
        self.assertNotIn("opaque-", repr(parsed))
        self.assertNotIn("opaque-", repr(entries))

    def test_docker_payload_continuations_are_scoped_to_the_container_and_stream(self):
        def row(payload, stream="stdout", container="api"):
            return json.dumps({"log": payload + "\n", "stream": stream,
                               "container": {"name": container}, "time": "2026-11-24T08:05:02Z"})

        opening = row("-----BEGIN PRIVATE KEY-----")
        rest = [row("healthy", stream="stderr"), row("listening", container="web"),
                row("synthetic-private-body"), row("-----END PRIVATE KEY-----"), row("ready")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "docker.log"
            path.write_text("\n".join([opening, *rest]) + "\n", encoding="utf-8")
            entries, _ = analyze_log(path, {})
            self.assertEqual([e["message"] for e in entries],
                             ["******", "healthy", "listening", "******", "******", "ready"])
            self.assertNotIn("synthetic-private-body", repr(entries))

            path.write_text(opening + "\n", encoding="utf-8")
            stop = Mock()
            stop.is_set.return_value = False
            def append_after_start(_timeout):
                with path.open("a", encoding="utf-8") as log:
                    log.write("\n".join(rest) + "\n")
                return False
            stop.wait.side_effect = append_after_start
            live = iterate_realtime(path, {}, stop)
            try:
                events = [next(live) for _ in rest]
            finally:
                live.close()
            self.assertEqual([e["message"] for e in events],
                             ["healthy", "listening", "******", "******", "ready"])
            self.assertNotIn("synthetic-private-body", repr(events))

    def test_multiline_field_can_open_a_pem_block_on_the_next_line(self):
        safe = mask_sensitive("private_key:\n-----BEGIN PRIVATE KEY-----\nsynthetic-body\n"
                              "-----END PRIVATE KEY-----\nINFO ready")
        self.assertNotIn("synthetic-body", safe)
        self.assertTrue(safe.endswith("INFO ready"))

    def test_live_reader_waits_for_complete_lines_and_keeps_existing_redaction_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            path.write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
            chunks = iter([b"opaque-key", b"-body\n-----END PRIVATE KEY-----\nERROR token=part",
                           b"-rest UTF-8: \xd0", b"\xb6\n"])
            stop = Mock()
            stop.is_set.return_value = False

            def append_chunk(timeout):
                with path.open("ab") as log_file:
                    log_file.write(next(chunks))

            stop.wait.side_effect = append_chunk
            entries = iterate_realtime(path, {"ERROR": True}, stop)
            try:
                self.assertEqual(next(entries)["raw"], "******")
                self.assertEqual(next(entries)["raw"], "******")
                entry = next(entries)
            finally:
                entries.close()

        self.assertEqual(stop.wait.call_count, 4)
        self.assertEqual(entry["raw"], "ERROR token=****** UTF-8: ж")
        self.assertEqual(entry["index"], 3)
        self.assertTrue(entry["is_danger"])
