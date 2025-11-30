import re

class ChromeParser:
    pattern = re.compile(
        r'^\[(\d+):(\d+):(\d{4})/(\d{6}\.\d{3}):([A-Z]+):([^\]]+)\]\s*(.*)$'
    )

    def match(self, line):
        return bool(self.pattern.match(line))

    def parse(self, line):
        m = self.pattern.match(line)
        if not m:
            return None

        pid, tid, mmdd, time_raw, level, source, message = m.groups()

        # ----------- ДАТА -----------
        month = mmdd[:2]
        day = mmdd[2:]

        # ----------- ВРЕМЯ -----------
        hh = time_raw[:2]
        mm = time_raw[2:4]
        ss = time_raw[4:]  # SS.mmm

        full_time = f"{month}-{day} {hh}:{mm}:{ss}"

        # ----------- ОЧИСТКА MESSAGE -----------
        # убираем вторую метку вида [19:24:14.602]
        message = re.sub(r"^\[\d{2}:\d{2}:\d{2}\.\d{3}\]\s*", "", message).strip()

        return {
            "format": "chrome",
            "raw": line,
            "date": f"{month}-{day}",
            "time": full_time,
            "level": level,
            "source": source.strip(),
            "message": message
        }
