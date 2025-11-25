import re

CUSTOM_PATTERN = re.compile(
    r"^\[([A-Z]+)\]\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(.*)$"
)

class CustomParser:
    def match(self, line):
        return bool(CUSTOM_PATTERN.match(line.strip()))

    def parse(self, line: str):
        raw = line.strip()
        m = CUSTOM_PATTERN.match(raw)
        if not m:
            return {
                "format": "custom",
                "raw": raw,
                "date": "N",
                "time": "N",
                "timestamp": "N",
                "level": "N",
                "source": "custom",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": raw,
            }

        level, date, time, message = m.groups()

        return {
            "format": "custom",
            "raw": raw,
            "date": date,
            "time": time,
            "timestamp": "N",
            "level": level,
            "source": "custom",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": message,
        }
