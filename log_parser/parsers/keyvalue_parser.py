import re

class KeyValueParser:
    def match(self, line):
        line = line.strip()
        if re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:", line):
            return False
        if re.search(r"\d{4}-\d{2}-\d{2}", line):
            return False
        if re.search(r"\d{2}:\d{2}:\d{2}", line):
            return False
        return bool(re.match(r"^[A-Za-z0-9_\-\.]+=.+", line))


    def parse(self, line):
        raw = line.strip()
        kv = {}

        for token in raw.split():
            if "=" in token:
                k, v = token.split("=", 1)
                kv[k] = v

        return {
            "format": "kv",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",

            "level": kv.get("level", "N"),
            "source": "kv",
            "module": "N",
            "thread": "N",

            "ids": [],
            "message": raw,

            "kv": kv
        }
