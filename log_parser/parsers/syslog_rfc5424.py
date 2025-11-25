import re

class SyslogRFC5424Parser:
    def match(self, line):
        return bool(re.match(r"\d{4}-\d{2}-\d{2}T", line))

    def parse(self, line):
        m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)", line)
        if not m:
            return {"format":"syslog_rfc5424","raw":line,"date":"N","time":"N","level":"N","message":line}

        date, time, usec, rest = m.groups()

        lvl_m = re.search(r"\[([A-Z]+)\]", rest)
        level = lvl_m.group(1) if lvl_m else "N"

        return {
            "format":"syslog_rfc5424",
            "raw": line,
            "date": date,
            "time": time,
            "usec": usec or "N",
            "level": level,
            "message": rest.strip()
        }
