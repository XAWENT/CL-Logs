import re

MONTHS = {
    "Jan": "01","Feb": "02","Mar": "03","Apr": "04",
    "May": "05","Jun": "06","Jul": "07","Aug": "08",
    "Sep": "09","Oct": "10","Nov": "11","Dec": "12"
}

class SyslogOldParser:

    # Проверка соответствия формату syslog
    def match(self, line):
        return bool(re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line))

    def parse(self, line):
        line = line.strip()

        m = re.match(
            r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$",
            line
        )
        if not m:
            return {
                "format": "syslog_old",
                "raw": line,
                "date": "N",
                "time": "N",
                "level": "N",
                "message": line
            }

        month, day, time, rest = m.groups()

        # ------------ Уровень лога ------------
        lvl_m = re.search(r"\[([A-Z]+)\]", rest)
        level = lvl_m.group(1) if lvl_m else "N"

        # ------------ Чистка сообщения ------------
        msg = rest

        # убрать префиксы workstation python[2031]:
        msg = re.sub(r"^[\w\-.]+(?:\[\d+\])?:\s*", "", msg)

        # убрать [ERROR], [INFO], [DEBUG]
        msg = re.sub(r"\[[A-Z]+\]", "", msg).strip()

        # удалить ISO timestamp внутри:
        msg = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?", "", msg)

        # удалить file.py:33 -
        msg = re.sub(r"[\w\-.]+:\d+\s*-\s*", "", msg)

        # финальная чистка
        msg = msg.strip()

        return {
            "format": "syslog_old",
            "raw": line,
            "date": f"{month} {day}",
            "time": time,
            "level": level,
            "message": msg
        }
