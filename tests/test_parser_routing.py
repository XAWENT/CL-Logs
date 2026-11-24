import json
import os
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from log_parser import parse_file, parse_line
from log_parser import parser_engine


FIXTURES = Path(__file__).resolve().parents[1] / "Test logs"
TIMESTAMP = "2024-01-15T10:30:45.123Z"


class ParserRoutingTests(unittest.TestCase):
    def assert_fields(self, line, **expected):
        entry = parse_line(line)
        for field, value in expected.items():
            self.assertEqual(entry[field], value, field)
        self.assertEqual(entry["raw"], line)

    def test_raw_preserves_indentation_and_trailing_spaces(self):
        for raw in ('  {"message":"test"} ', '    at example.run(example.java:7)  ', '# Warning: disk full'):
            with self.subTest(raw=raw):
                self.assertEqual(parse_line(raw + "\r\n")["raw"], raw)

    def test_discovery_does_not_depend_on_directory_order(self):
        listdir = os.listdir

        def load_in_order(reverse):
            with (
                patch.object(parser_engine, "_parsers_cache", None),
                patch.object(
                    parser_engine.os,
                    "listdir",
                    side_effect=lambda directory: sorted(listdir(directory), reverse=reverse),
                ),
            ):
                return [type(parser).__name__ for parser in parser_engine._load_parsers()]

        order = load_in_order(reverse=False)
        self.assertEqual(order, load_in_order(reverse=True))
        self.assertLess(order.index("DockerParser"), order.index("JSONParser"))
        self.assertLess(order.index("MySQLParser"), order.index("SyslogRFC5424Parser"))

    def test_discovery_accepts_a_plugin_without_priority(self):
        class ExampleParser:
            def match(self, line):
                return line == "plugin input"

            def parse(self, line):
                return {"format": "example", "raw": line, "message": line}

        with (
            patch.object(parser_engine, "_parsers_cache", None),
            patch.object(parser_engine.os, "listdir", return_value=["example_parser.py"]),
            patch.object(
                parser_engine.importlib,
                "import_module",
                return_value=SimpleNamespace(ExampleParser=ExampleParser),
            ) as import_module,
        ):
            self.assert_fields("plugin input", format="example", message="plugin input")
        import_module.assert_called_once_with("log_parser.parsers.example_parser")

    def test_ordinary_json_uses_text_fields(self):
        line = json.dumps({
            "timestamp": 1700000000,
            "level": "WARNING",
            "message": {"detail": "slow"},
            "ids": 42,
            "source": None,
            "raw": [],
            "format": "application",
        })
        self.assert_fields(
            line,
            format="json",
            timestamp="1700000000",
            level="WARN",
            message='{"detail": "slow"}',
            ids=[42],
            source="N",
        )

    def test_ordinary_json_splits_iso_timestamp_for_display(self):
        self.assert_fields(
            json.dumps({"timestamp": "2024-01-15T10:30:45.123456789+02:00", "message": "ready"}),
            format="json",
            timestamp="2024-01-15T10:30:45.123456789+02:00",
            date="2024-01-15",
            time="10:30:45.123456789",
        )
        self.assert_fields(
            json.dumps({"timestamp": TIMESTAMP, "date": "custom date", "time": "custom time"}),
            date="custom date",
            time="custom time",
        )

    def test_specialized_json_uses_distinguishing_fields(self):
        cases = [
            (
                {"log": "connection closed\n", "stream": "stderr", "time": TIMESTAMP, "namespace": "test"},
                {"format": "docker_json", "timestamp": TIMESTAMP, "level": "ERROR", "module": "stderr",
                 "message": "connection closed"},
            ),
            (
                {"@timestamp": TIMESTAMP, "@message": "request handled", "level": "INFO"},
                {"format": "aws_cloudwatch_json", "timestamp": TIMESTAMP, "level": "INFO",
                 "message": "request handled"},
            ),
            (
                {"ts": 1700000000, "msg": "pod started", "logger": "controller", "level": "INFO"},
                {"format": "k8s_json", "timestamp": "1700000000", "source": "controller",
                 "message": "pod started"},
            ),
        ]
        for data, expected in cases:
            with self.subTest(format=expected["format"]):
                self.assert_fields(json.dumps(data), **expected)

    def test_iso_text_preserves_service_specific_and_generic_fields(self):
        request_id = "5e593a1f-361c-4f67-a201-aaced5c4bf43"
        cases = [
            (
                "0 [ERROR] [MY-010020] [Server] Data dictionary initialization failed",
                {"format": "mysql", "thread": "0", "module": "Server", "level": "ERROR",
                 "message": "Data dictionary initialization failed"},
            ),
            (
                "stderr server closed the connection",
                {"format": "docker", "module": "stderr", "level": "ERROR",
                 "message": "server closed the connection"},
            ),
            (
                f"{request_id} WARN request took longer",
                {"format": "aws_cloudwatch", "thread": request_id, "level": "WARN",
                 "message": "request took longer"},
            ),
            (
                "[INFO] application started",
                {"format": "syslog_rfc5424", "level": "INFO", "message": "application started"},
            ),
            (
                "application started",
                {"format": "syslog_rfc5424", "level": "INFO", "message": "application started"},
            ),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                self.assert_fields(f"{TIMESTAMP} {body}", timestamp=TIMESTAMP, **expected)

    def test_cri_removes_record_tag_and_uses_explicit_severity(self):
        cases = (
            ("stdout F ERROR gateway timeout", "stdout", "ERROR", "ERROR gateway timeout"),
            ("stderr F INFO bootstrap complete", "stderr", "INFO", "INFO bootstrap complete"),
            ("stdout P [WARN] retrying ", "stdout", "WARN", "[WARN] retrying"),
            ("stderr F", "stderr", "ERROR", ""),
        )
        for body, stream, level, message in cases:
            with self.subTest(body=body):
                self.assert_fields(f"{TIMESTAMP} {body}", format="k8s_cri", module=stream,
                                   level=level, message=message)

    def test_docker_formats_prefer_explicit_severity_to_stream_and_message_text(self):
        cases = (
            (f"{TIMESTAMP} stdout ERROR: request timed out", "docker", "ERROR"),
            (f"{TIMESTAMP} checkout | INFO previous ERROR cleared", "docker", "INFO"),
            (json.dumps({"log": "[INFO] ready\n", "stream": "stderr", "time": TIMESTAMP}), "docker_json", "INFO"),
            (json.dumps({"log": "FATAL process crashed\n", "stream": "stdout", "time": TIMESTAMP}),
             "docker_json", "CRITICAL"),
        )
        for line, format_name, level in cases:
            with self.subTest(line=line):
                self.assert_fields(line, format=format_name, level=level)

    def test_journal_and_legacy_syslog_have_separate_routes(self):
        self.assert_fields(
            "Jan 15 10:30:45 host systemd[1]: Started service",
            format="systemd",
            thread="1",
            message="Started service",
        )
        self.assert_fields(
            "Jan 15 10:30:45 host sshd[1]: Started service",
            format="syslog_old",
        )

    def test_existing_fixtures_retain_their_classifications(self):
        expected_formats = {
            "discord.log": {"python_logging": 273},
            "latest.log": {"minecraft": 30, "generic": 62},
        }
        for filename, expected in expected_formats.items():
            with self.subTest(filename=filename):
                formats = Counter(entry["format"] for entry in parse_file(FIXTURES / filename))
                self.assertEqual(formats, expected)


if __name__ == "__main__":
    unittest.main()
