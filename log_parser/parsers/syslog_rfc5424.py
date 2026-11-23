import re


class SyslogRFC5424Parser:
    # Keep the ISO timestamp prefix handler behind service-specific formats.
    priority = -100
    _pattern = re.compile(
        r"^((\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
        r"(?:Z|[+-]\d{2}:?\d{2})?)(?:\s+(.*))?$"
    )
    _level_prefix = re.compile(
        r"^(?:\[(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|FATAL)\]"
        r"|(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|FATAL):?)"
        r"(?:\s+|$)",
        re.IGNORECASE,
    )

    def match(self, line):
        return bool(self._pattern.match(line.strip()))

    def parse(self, line):
        raw = line.strip()
        match = self._pattern.match(raw)
        if not match:
            return {"format": "syslog_rfc5424", "raw": raw, "source": "syslog", "message": raw}

        timestamp, date, time, message = match.groups()
        message = message or ""
        severity = self._level_prefix.match(message)
        level = "N"
        if severity:
            level = severity.group(1) or severity.group(2)
            message = message[severity.end():]

        return {
            "format": "syslog_rfc5424",
            "raw": raw,
            "date": date,
            "time": time,
            "timestamp": timestamp,
            "level": level,
            "source": "syslog",
            "message": message,
        }
