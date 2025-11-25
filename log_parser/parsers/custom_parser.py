"""Parser for custom `[LEVEL] YYYY-MM-DD HH:MM:SS ...` log format."""

import re

CUSTOM_PATTERN = re.compile(
    r"^\[([A-Z]+)\]\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(.*)$"
)


def parse(line: str):
    line = line.strip()
    m = CUSTOM_PATTERN.match(line)
    if not m:
        return None

    level, date, time, message = m.groups()

    return {
        "format": "custom",
        "raw": line,
        "date": date,
        "time": time,
        "level": level,
        "message": message
    }
