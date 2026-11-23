from __future__ import annotations
import importlib
import json
import os
import typing

from log_parser.fallback import fallback_parse
from log_parser.redaction import LogRedactor, mask_sensitive


STANDARD_FIELDS = {
    "format": "N",
    "raw": "N",

    "date": "N",
    "time": "N",
    "timestamp": "N",

    "level": "N",
    "source": "N",
    "module": "N",
    "thread": "N",

    "ids": [],
    "message": "N",
}

LEVEL_ALIASES = {
    "TRACE": "DEBUG",
    "VERBOSE": "DEBUG",
    "NOTICE": "INFO",
    "INFORMATION": "INFO",
    "INFORMATIONAL": "INFO",
    "WARNING": "WARN",
    "WRN": "WARN",
    "ERR": "ERROR",
    "SEVERE": "ERROR",
    "EMERG": "CRITICAL",
    "ALERT": "CRITICAL",
    "CRIT": "CRITICAL",
    "PANIC": "CRITICAL",
    "FATAL": "CRITICAL",
}

CANONICAL_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}


def normalize_level(level: object, message: str = "") -> str:
    lvl = str(level or "N").strip().upper()

    if lvl in LEVEL_ALIASES:
        lvl = LEVEL_ALIASES[lvl]

    if lvl in CANONICAL_LEVELS:
        return lvl

    msg = (message or "").upper()
    if any(k in msg for k in ("PANIC", "FATAL", "CRITICAL", "EMERG", "ALERT")):
        return "CRITICAL"
    if any(k in msg for k in ("ERROR", "EXCEPTION", "FAILED", "FAILURE", "TRACEBACK")):
        return "ERROR"
    if any(k in msg for k in ("WARN", "WARNING", "DEPRECATED", "RETRY")):
        return "WARN"
    if any(k in msg for k in ("DEBUG", "TRACE", "VERBOSE")):
        return "DEBUG"
    if any(k in msg for k in ("INFO", "STARTED", "READY", "LISTENING")):
        return "INFO"

    return "N"

def normalize(parsed: dict):
    out = {}

    for key, default in STANDARD_FIELDS.items():
        if key == "ids":
            continue
        value = parsed.get(key)
        if value is None:
            value = default
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif not isinstance(value, str):
            value = str(value)
        out[key] = value

    out["level"] = normalize_level(out["level"], out["message"])

    ids = parsed.get("ids")
    if ids is None:
        ids = []
    out["ids"] = ids if isinstance(ids, list) else [ids]

    return out


_parsers_cache = None

def _load_parsers():
    global _parsers_cache
    if _parsers_cache is not None:
        return _parsers_cache

    parsers = []
    base = os.path.dirname(__file__)
    pars_dir = os.path.join(base, "parsers")

    for fname in sorted(os.listdir(pars_dir)):
        if fname.endswith(".py") and not fname.startswith("_"):

            modname = fname[:-3]
            module = importlib.import_module(f"log_parser.parsers.{modname}")

            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type):

                    if obj in (str, int, float, list, dict, tuple, set, type, object):
                        continue

                    if obj is typing.Any:
                        continue

                    try:
                        instance = obj()
                    except Exception:
                        continue

                    if hasattr(instance, "match") and hasattr(instance, "parse"):
                        parsers.append(instance)

    # Python's stable sort keeps module and class discovery order for ties.
    parsers.sort(key=lambda parser: getattr(parser, "priority", 0), reverse=True)
    _parsers_cache = parsers
    return parsers

def parse_line(line: str):
    return _parse_redacted_line(mask_sensitive(line.rstrip("\r\n")))


def _parse_redacted_line(line: str):
    parsers = _load_parsers()

    for parser in parsers:
        try:
            if parser.match(line):
                entry = normalize(parser.parse(line))
                entry["raw"] = line
                return entry
        except Exception:
            return normalize({
                "format": "parser_error",
                "raw": line,
                "level": "ERROR",
                "message": f"Parser failed: {type(parser).__name__}",
            })

    entry = normalize(fallback_parse(line))
    entry["raw"] = line
    return entry


def parse_file(path: str):
    redactor = LogRedactor()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield _parse_redacted_line(redactor.redact(line.rstrip("\r\n")))


def get_errors(log_stream):
    for log in log_stream:
        lvl = log.get("level", "N")
        if lvl in ("ERROR", "FATAL", "CRITICAL"):
            yield log
