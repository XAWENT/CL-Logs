import re

class SyslogRFC5424Parser:
    def match(self, line):
        return bool(re.match(r"\d{4}-\d{2}-\d{2}T", line))

    def parse(self, line):
        raw = line.strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)", raw)
        if not m:
            return {
                "format": "syslog_rfc5424",
                "raw": raw,
                "date": "N",
                "time": "N",
                "timestamp": "N",
                "level": "N",
                "source": "syslog",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": raw
            }

        date, time, usec, rest = m.groups()

        lvl_m = re.search(r"\[([A-Z]+)\]", rest)
        level = lvl_m.group(1) if lvl_m else "N"

        return {
            "format": "syslog_rfc5424",
            "raw": raw,
            "date": date,
            "time": time,
            "timestamp": usec or "N",

            "level": level,
            "source": "syslog",
            "module": "N",
            "thread": "N",

            "ids": [],
            "message": rest.strip()
        }
