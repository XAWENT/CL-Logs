"""Parser for Minecraft ``latest.log`` format.

Minecraft servers produce logs where each line typically looks like::

    [10:23:45] [Server thread/INFO]: Done (1.234s)! For help, type "help"

The timestamp does not include a date; we assume the current date for
parsing purposes. The parser extracts the thread, level and message
fields and returns them along with an ISO formatted timestamp.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict


class MinecraftParser:
    """Parse Minecraft server log entries from ``latest.log``."""

    _regex = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] \[([^\]]+)/(\w+)\]:\s*(.*)$")

    def match(self, line: str) -> bool:
        return bool(self._regex.match(line.strip()))

    def parse(self, line: str) -> Dict[str, Any]:
        m = self._regex.match(line.strip())
        if not m:
            raise ValueError("Not a Minecraft log line")
        time_str, thread, level, message = m.groups()
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp_iso = f"{today}T{time_str}"
        return {
            "format": "minecraft",
            "timestamp": timestamp_iso,
            "thread": thread,
            "level": level.upper(),
            "message": message,
            "raw": line.strip(),
        }