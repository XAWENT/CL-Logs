import re
from typing import Dict, Any


class PythonLoggingParser:
    _pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+-\s+"  # timestamp
        r"([\w\.]+)\s+-\s+"  # logger name
        r"([A-Z]+)\s+-\s+"   # level
        r"(.*)$"             # message
    )

    _simple_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3}))\s+-\s+"
        r"([A-Z]+)\s+-\s+(.*)$"
    )

    _bracket_pattern = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+\[([A-Z]+)\s*\]\s+([\w.]+):\s*(.*)$"
    )

    _slash_pattern = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*\[([^\]/]+)/([^\]]+)\]\s*(.*)$"
    )

    def match(self, line: str) -> bool:
        stripped = line.strip()
        return bool(
            self._pattern.match(stripped)
            or self._simple_pattern.match(stripped)
            or self._bracket_pattern.match(stripped)
            or self._slash_pattern.match(stripped)
        )

    def _build_result(self, raw: str, timestamp: str, level: str, logger: str, message: str) -> Dict[str, Any]:
        date_part, time_part = timestamp.split()
        time_part = time_part.replace(",", ".")

        return {
            "format": "python_logging",
            "raw": raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp.replace(" ", "T"),
            "level": level,
            "source": logger,
            "module": logger.rsplit(".", 1)[-1] if "." in logger else logger,
            "thread": "N",
            "ids": [],
            "message": message,
        }

    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()

        m = self._pattern.match(raw)
        if m:
            timestamp, logger, level, message = m.groups()
            return self._build_result(raw, timestamp, level, logger, message)

        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            return self._build_result(raw, timestamp, level, "python", message)

        m = self._bracket_pattern.match(raw)
        if m:
            timestamp, level, logger, message = m.groups()
            return self._build_result(raw, timestamp, level, logger, message)

        m = self._slash_pattern.match(raw)
        if m:
            timestamp, logger, level, message = m.groups()
            return self._build_result(raw, timestamp, level, logger, message)

        return {
            "format": "python_logging",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "python",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
