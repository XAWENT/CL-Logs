import re

class MinecraftParser:
    def match(self, line):
        return bool(re.match(r"\[\d{2}:\d{2}:\d{2}\]", line.strip()))

    def parse(self, line):
        m = re.match(r"\[(\d{2}:\d{2}:\d{2})\] \[([^/]+)/([A-Z]+)\]:\s*(.*)", line.strip())
        if not m:
            return {"format":"minecraft","raw":line,"date":"N","time":"N","level":"N","message":line}

        time, thread, level, msg = m.groups()

        return {
            "format":"minecraft",
            "raw": line,
            "date": "N",
            "time": time,
            "level": level,
            "thread": thread,
            "message": msg
        }
