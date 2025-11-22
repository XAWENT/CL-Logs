from __future__ import annotations
"""
Heuristic fallback parser for arbitrary log lines.

Теперь поддерживает:
- полный ISO-8601: 2025-10-25T15:08:48.903642+03:00
- timestamp с микросекундами
- timezone offset
- спец-символы Linux (#012 → \n)
"""

import re
from datetime import datetime
from typing import Any, Dict, Tuple

# ============================
# TIMESTAMP REGEXES
# ============================

ISO_FULL = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,6}\+\d{2}:\d{2}"
ISO_SECOND = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
DATE_TIME = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
SYSLOG = r"[A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2}"

TIMESTAMP_PATTERNS = [
    ISO_FULL,
    ISO_SECOND,
    DATE_TIME,
    SYSLOG,
    r"\d{2}:\d{2}:\d{2}",
]

ERROR_LEVELS = [
    "ERROR", "WARN", "WARNING", "FATAL", "CRITICAL",
    "SEVERE", "ERR"
]

_KV_REGEX = re.compile(r"(\w+)=([\"'].*?[\"']|\S+)")


# ============================
# Linux escape cleaner
# ============================

def _clean_linux_escapes(text: str) -> str:
    if not isinstance(text, str):
        return text
    return (
        text.replace("#012", "\n")
            .replace("#011", "\t")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
    )


# ============================
# timestamp extractor
# ============================

def _extract_timestamp(s: str) -> Tuple[str | None, str]:
    for pattern in TIMESTAMP_PATTERNS:
        m = re.search(pattern, s)
        if not m:
            continue

        ts_raw = m.group(0)

        # try parsing iso full
        try:
            if re.fullmatch(ISO_FULL, ts_raw):
                dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S.%f%z")
                ts_iso = dt.isoformat()
            elif re.fullmatch(ISO_SECOND, ts_raw):
                dt = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%S")
                ts_iso = dt.isoformat()
            elif re.fullmatch(DATE_TIME, ts_raw):
                dt = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                ts_iso = dt.isoformat()
            elif re.fullmatch(SYSLOG, ts_raw):
                try:
                    dt = datetime.strptime(ts_raw, "%b %d %H:%M:%S")
                    dt = dt.replace(year=datetime.now().year)
                    ts_iso = dt.isoformat()
                except:
                    ts_iso = ts_raw
            else:
                ts_iso = ts_raw
        except:
            ts_iso = ts_raw

        rest = s.replace(ts_raw, "", 1).strip()

        return ts_iso, rest

    return None, s


# ============================
# log level extractor
# ============================

def _extract_level(s: str) -> Tuple[str | None, str]:
    up = s.upper()
    for lvl in ERROR_LEVELS:
        if lvl in up:
            idx = up.find(lvl)
            cleaned = s[:idx] + s[idx+len(lvl):]
            return lvl, cleaned.strip()
    return None, s


# ============================
# key=value extractor
# ============================

def _extract_kv_pairs(s: str) -> Tuple[Dict[str, Any], str]:
    mapping = {}
    spans = []

    for m in _KV_REGEX.finditer(s):
        key = m.group(1)
        value = m.group(2)
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            value = value[1:-1]
        mapping[key] = value
        spans.append(m.span())

    if not spans:
        return {}, s

    parts = []
    last = 0
    for start, end in spans:
        parts.append(s[last:start])
        last = end
    parts.append(s[last:])

    remainder = "".join(parts).strip()
    return mapping, remainder


# ============================
# MAIN FALLBACK PARSER
# ============================

def fallback_parse(line: str) -> Dict[str, Any]:
    result = {
        "format": "generic",
        "raw": line
    }

    s = line.strip()

    ts, s = _extract_timestamp(s)
    if ts:
        result["timestamp"] = ts

    lvl, s = _extract_level(s)
    if lvl:
        result["level"] = lvl

    kv, s = _extract_kv_pairs(s)
    if kv:
        result["kv"] = kv

    cleaned = _clean_linux_escapes(s)
    if cleaned:
        result["message"] = cleaned.strip()

    return result