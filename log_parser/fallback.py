from __future__ import annotations
import re

DATE_PATTERNS = [
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",     # 15.11.23 15/11/2023 15-11-23
    r"\b\d{4}-\d{2}-\d{2}\b",                  # 2025-11-24
    r"\b[A-Z][a-z]{2}\s+\d{1,2}\b",            # Nov 24  (syslog)
]

TIME_PATTERNS = [
    r"\b\d{2}:\d{2}:\d{2}\b",
    r"\b\d{2}:\d{2}\b",
    r"\b\d{6}\.\d{3}\b",                       # 182414.603
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

LEVELS = [
    "ERROR", "ERR", "WARN", "WARNING",
    "INFO", "DEBUG", "CRITICAL", "FATAL"
]

LEVEL_ALIAS = {
    "WARNING": "WARN",
    "ERR": "ERROR"
}

def detect_level(text: str):
    parts = re.findall(r"\b[A-Z]{3,9}\b", text.upper())
    for p in parts:
        if p in LEVELS:
            return LEVEL_ALIAS.get(p, p)
    return "N"

SOURCE_PATTERNS = [
    r"\b[A-Za-z0-9_\-]+\.(cpp|cc|py|js|go|rs)\b",
    r"\b[A-Za-z0-9_\-]+\[[0-9]+\]:",
    r"\b[A-Za-z0-9_\-]+(?:\s+service)?\b",
]

def extract_source(line: str):
    for p in SOURCE_PATTERNS:
        m = re.search(p, line)
        if m:
            return m.group(0).replace(":", "")
    return "generic"

def clean_message(line: str):
    msg = line

    for p in DATE_PATTERNS + TIME_PATTERNS:
        msg = re.sub(p, "", msg)

    msg = re.sub(r"\[[A-Za-z0-9_]+\]", "", msg)

    for lvl in LEVELS:
        msg = re.sub(rf"\b{lvl}\b", "", msg, flags=re.IGNORECASE)

    msg = msg.replace("::", ":")

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
