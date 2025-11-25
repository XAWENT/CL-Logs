import re

class MinecraftParser:
    def match(self, line):
        return bool(re.match(r"\[\d{2}:\d{2}:\d{2}\]", line.strip()))

    def parse(self, line):
        raw = line.strip()

        m = re.match(
            r"\[(\d{2}:\d{2}:\d{2})\]\s+\[([^/]+)/([A-Z]+)\]:\s*(.*)",
            raw
        )
        if not m:
            return {
                "format": "minecraft",
                "raw": raw,
                "date": "N",
                "time": "N",
                "timestamp": "N",
                "level": "N",
                "source": "generic",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": raw
            }

        time, thread, level, msg = m.groups()

        return {
            "format": "minecraft",
            "raw": raw,
            "date": "N",
            "time": time,
            "timestamp": "N",
            "level": level,
            "source": "minecraft",
            "module": "N",
            "thread": thread,
            "ids": [],
            "message": msg
        }
