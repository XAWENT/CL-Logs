"""Parser for custom `[LEVEL] YYYY-MM-DD HH:MM:SS ...` log format.

This parser recognizes log lines that begin with a severity level in
square brackets followed by a timestamp. The remainder of the line
is treated as a free‑form message. Examples::

    [ERROR] 2025-11-15 14:32:10 Something bad happened
    [WARN]  2025-11-15 14:33:00 A mild warning occurred

Both the timestamp and severity are extracted, converted where
possible, and returned along with the message and the raw input.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict


class CustomParser:
    """Parse simple `[LEVEL] YYYY-MM-DD HH:MM:SS` log entries."""

    _regex = re.compile(
        r"^\[([A-Za-z]+)\]\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(.*)$"
    )

    def match(self, line: str) -> bool:
        return bool(self._regex.match(line.strip()))

    def parse(self, line: str) -> Dict[str, Any]:
        m = self._regex.match(line.strip())
        if not m:
            raise ValueError("Not a custom [LEVEL] line")
        level, timestamp_str, message = m.groups()
        # attempt to parse timestamp into ISO; if fails, keep raw
        try:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").isoformat()
        except Exception:
            ts = timestamp_str
        return {
            "format": "custom",
            "level": level.upper(),
            "timestamp": ts,
            "message": message.strip(),
            "raw": line.strip(),
        }