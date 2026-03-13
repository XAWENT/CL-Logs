from __future__ import annotations
import re

LEVEL_CANONICAL = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}

LEVEL_MAP = {
    "TRACE": "DEBUG",
    "VERBOSE": "DEBUG",
    "DBG": "DEBUG",
    "DEBUG": "DEBUG",

    "INFO": "INFO",
    "INFORMATION": "INFO",
    "INFORMATIONAL": "INFO",
    "NOTICE": "INFO",

    "WARN": "WARN",
    "WARNING": "WARN",
    "WRN": "WARN",

    "ERR": "ERROR",
    "ERROR": "ERROR",
    "SEVERE": "ERROR",
    "EXCEPTION": "ERROR",

    "CRIT": "CRITICAL",
    "CRITICAL": "CRITICAL",
    "ALERT": "CRITICAL",
    "EMERG": "CRITICAL",
    "EMERGENCY": "CRITICAL",
    "PANIC": "CRITICAL",
    "FATAL": "CRITICAL",
}

DATE_PATTERNS = [
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",     # 15.11.23 15/11/2023 15-11-23
    r"\b\d{4}-\d{2}-\d{2}\b",                  # 2025-11-24
    r"\b[A-Z][a-z]{2}\s+\d{1,2}\b",            # Nov 24  (syslog)
]

TIME_PATTERNS = [
    r"\b\d{2}:\d{2}:\d{2}\b",
    r"\b\d{2}:\d{2}\b",
    r"\b\d{6}\.\d{3}\b",                       # 182414.603
    r"\b\d{2}:\d{2}:\d{2}[.,]\d{3,6}\b",      # 12:34:56.123456
]

def extract_date(line: str):
    for p in DATE_PATTERNS:
        m = re.search(p, line)
        if m:
            return m.group(0)
    return "N"

def extract_time(line: str):
    for p in TIME_PATTERNS:
        m = re.search(p, line)
        if m:
            t = m.group(0)
            if len(t) == 6 or "." in t:        # форматы типа 192414.603
                return f"{t[:2]}:{t[2:4]}:{t[4:]}"
            return t
    return "N"

def detect_level(text: str):
    upper = text.upper()

    # 1) частые структурные формы: [error], level=warn, severity:critical
    direct_patterns = [
        r"\[(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|ALERT|EMERG(?:ENCY)?|PANIC|FATAL)\]",
        r"\b(?:LEVEL|SEVERITY|PRIORITY)\s*[:=]\s*(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|ALERT|EMERG(?:ENCY)?|PANIC|FATAL)\b",
        r"\b(TRC|DBG|INF|WRN|ERR|CRT)\b",
    ]
    for pat in direct_patterns:
        m = re.search(pat, upper)
        if m:
            raw = m.group(1)
            raw = {
                "TRC": "TRACE",
                "DBG": "DEBUG",
                "INF": "INFO",
                "WRN": "WARN",
                "CRT": "CRIT",
            }.get(raw, raw)
            return LEVEL_MAP.get(raw, "N")

    # 2) fallback по токенам
    parts = re.findall(r"\b[A-Z]{3,12}\b", upper)
    for p in parts:
        if p in LEVEL_MAP:
            return LEVEL_MAP[p]

    # 3) эвристика по содержимому
    if any(k in upper for k in ("PANIC", "FATAL", "EMERG", "ALERT", "CRITICAL")):
        return "CRITICAL"
    if any(k in upper for k in ("ERROR", "EXCEPTION", "TRACEBACK", "FAILED", "FAILURE")):
        return "ERROR"
    if any(k in upper for k in ("WARN", "WARNING", "DEPRECATED", "RETRY")):
        return "WARN"
    if any(k in upper for k in ("DEBUG", "TRACE", "VERBOSE")):
        return "DEBUG"
    if any(k in upper for k in ("INFO", "STARTED", "READY", "LISTENING", "CONNECTED")):
        return "INFO"

    return "N"

SOURCE_PATTERNS = [
    r"\b([A-Za-z0-9_.\-]+)\[(\d+)\]:",                 # service[123]:
    r"\b([A-Za-z0-9_.\-]+)\.(cpp|cc|py|js|go|rs|java|cs|php)\b",
    r"\b(?:service|app|module|logger|component)\s*[:=]\s*([A-Za-z0-9_.\-]+)\b",
    r"\b([A-Za-z0-9_.\-/]+):(\d+)\b",                   # file.py:42
    r"\b[A-Za-z0-9_\-]+\.(cpp|cc|py|js|go|rs)\b",
    r"\b[A-Za-z0-9_\-]+\[[0-9]+\]:",
    r"\b[A-Za-z0-9_\-]+(?:\s+service)?\b",
]

def extract_source(line: str):
    for p in SOURCE_PATTERNS:
        m = re.search(p, line)
        if m:
            if m.lastindex:
                g1 = m.group(1)
                if g1:
                    return g1
            return m.group(0).replace(":", "")
    return "generic"

def clean_message(line: str):
    msg = line

    for p in DATE_PATTERNS + TIME_PATTERNS:
        msg = re.sub(p, "", msg)

    msg = re.sub(r"\[[A-Za-z0-9_]+\]", "", msg)

    # удаляем level=warn / severity:error
    msg = re.sub(
        r"\b(?:LEVEL|SEVERITY|PRIORITY)\s*[:=]\s*(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|ALERT|EMERG(?:ENCY)?|PANIC|FATAL)\b",
        "",
        msg,
        flags=re.IGNORECASE,
    )

    for lvl in LEVEL_MAP:
        msg = re.sub(rf"\b{lvl}\b", "", msg, flags=re.IGNORECASE)

    msg = msg.replace("::", ":")
    msg = re.sub(r"\s+[|;,-]\s*$", "", msg)

    msg = " ".join(msg.split()).strip()

    return msg if msg else line
def fallback_parse(line: str):
    raw = line.strip()

    date = extract_date(raw)
    time = extract_time(raw)
    level = detect_level(raw)
    source = extract_source(raw)
    message = clean_message(raw)

    return {
        "format": "generic",
        "raw": raw,
        "date": date,
        "time": time,
        "timestamp": "N",

        "level": level,
        "source": source,
        "module": "N",
        "thread": "N",

        "message": message,
    }
