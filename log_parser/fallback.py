from __future__ import annotations
import re

# ------------------------------
# UNIVERSAL DATE/TIME DETECTION
# ------------------------------

DATE_PATTERNS = [
    r"\b\d{1,2}\.\d{1,2}\.\d{2}\b",
    r"\b\d{1,2}\.\d{1,2}\.\d{4}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    r"\b\d{1,2}\.\d{1,2}\b",
]

TIME_PATTERNS = [
    r"\b\d{2}:\d{2}:\d{2}\b",
    r"\b\d{2}:\d{2}\b",
]

def extract_date_and_time(line: str):
    date = "N"
    time = "N"

    for p in DATE_PATTERNS:
        m = re.search(p, line)
        if m:
            date = m.group(0)
            break

    for p in TIME_PATTERNS:
        m = re.search(p, line)
        if m:
            time = m.group(0)
            break

    return date, time


# ------------------------------
# ADVANCED FALLBACK PARSER (PRO)
# ------------------------------

LEVELS = [
    "ERROR", "WARN", "WARNING", "INFO",
    "DEBUG", "CRITICAL", "FATAL"
]

LEVEL_ALIAS = {
    "WARNING": "WARN"
}

TAG_PATTERN = re.compile(r"\[([A-Za-z0-9_\- ]+)\]")
ID_PATTERN  = re.compile(r"(#\d+|\bERR\d+\b|\bE\d{3,5}\b)")

def detect_level(text: str):
    up = text.upper()
    for lvl in LEVELS:
        if lvl in up:
            return LEVEL_ALIAS.get(lvl, lvl)
    return "N"

def extract_source(line: str):
    m = TAG_PATTERN.search(line)
    if m:
        return m.group(1)
    return "generic"

def clean_message(line: str):
    line = TAG_PATTERN.sub("", line)

    for p in DATE_PATTERNS + TIME_PATTERNS:
        line = re.sub(p, "", line)

    for lvl in LEVELS:
        line = re.sub(rf"\b{lvl}\b", "", line, flags=re.IGNORECASE)

    return " ".join(line.split()).strip()


def fallback_parse(line: str):
    raw = line.strip()
    date, time = extract_date_and_time(raw)
    level = detect_level(raw)
    source = extract_source(raw)
    error_ids = ID_PATTERN.findall(raw) or []
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

        "ids": error_ids,
        "message": message,
    }
