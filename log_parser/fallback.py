from __future__ import annotations
import re

# ------------------------------
# UNIVERSAL DATE/TIME DETECTION
# ------------------------------

DATE_PATTERNS = [
    r"\b\d{1,2}\.\d{1,2}\.\d{2}\b",          # 15.11.23
    r"\b\d{1,2}\.\d{1,2}\.\d{4}\b",          # 15.11.2023
    r"\b\d{4}-\d{2}-\d{2}\b",                # 2023-11-15
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",            # 15/11/2023
    r"\b\d{1,2}\.\d{1,2}\b",                 # 15.11 (без года)
]

TIME_PATTERNS = [
    r"\b\d{2}:\d{2}:\d{2}\b",                # 11:33:34
    r"\b\d{2}:\d{2}\b",                      # 11:33
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
# FALLBACK PARSER
# ------------------------------

def fallback_parse(line):
    line = line.strip()

    date, time = extract_date_and_time(line)

    LEVELS = ["ERROR", "WARN", "WARNING", "INFO", "DEBUG", "CRITICAL", "FATAL"]
    level = "N"

    up = line.upper()
    for lvl in LEVELS:
        if lvl in up:
            level = lvl
            break

    return {
        "format": "generic",
        "raw": line,
        "date": date,
        "time": time,
        "level": level,
        "message": line
    }
