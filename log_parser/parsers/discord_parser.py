import re


DISCORD_PATTERNS = (
    re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*\[([^\]/]+)/([^\]]+)\]\s*(.*)$"
    ),
    re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[([^\]/]+)/([^\]]+)\]\s*(.*)$"
    ),
)


class DiscordParser:
    def match(self, line):
        raw = line.strip()
        if not raw:
            return False

        lowered = raw.lower()
        if "discord" not in lowered:
            return False

        return any(pattern.match(raw) for pattern in DISCORD_PATTERNS)

    def parse(self, line):
        raw = line.strip()

        for pattern in DISCORD_PATTERNS:
            match = pattern.match(raw)
            if not match:
                continue

            timestamp, source, level, message = match.groups()
            date, time = timestamp.split()

            return {
                "format": "discord",
                "raw": raw,
                "date": date,
                "time": time,
                "timestamp": timestamp,
                "level": level,
                "source": source.strip(),
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": message.strip(),
            }

        return {
            "format": "discord",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "discord",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw,
        }
