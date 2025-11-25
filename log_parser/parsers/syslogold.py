import re

MONTHS = {
    "Jan": "01","Feb": "02","Mar": "03","Apr": "04",
    "May": "05","Jun": "06","Jul": "07","Aug": "08",
    "Sep": "09","Oct": "10","Nov": "11","Dec": "12"
}

class SyslogOldParser:
    def match(self, line):
        return bool(re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line))

    def parse(self, line):
        raw = line.strip()
        m = re.match(
            r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$",
            raw
        )

        if not m:
            return {
                "format": "syslog_old",
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

        month, day, time, rest = m.groups()
        lvl_m = re.search(r"\[([A-Z]+)\]", rest)
        level = lvl_m.group(1) if lvl_m else "N"

        msg = rest
        msg = re.sub(r"^[\w\-.]+(?:\[\d+\])?:\s*", "", msg)
        msg = re.sub(r"\[[A-Z]+\]", "", msg).strip()
        msg = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?", "", msg)
        msg = re.sub(r"[\w\-.]+:\d+\s*-\s*", "", msg).strip()

        return {
            "format": "syslog_old",
            "raw": raw,
            "date": f"{month} {day}",
            "time": time,
            "timestamp": "N",

            "level": level,
            "source": "syslog",
            "module": "N",
            "thread": "N",

            "ids": [],
            "message": msg
        }
