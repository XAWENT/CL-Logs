from __future__ import annotations
import os
import importlib
from log_parser.fallback import fallback_parse


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
        out[key] = parsed.get(key, default)

    out["level"] = normalize_level(out.get("level"), str(out.get("message", "")))

    if not isinstance(out["ids"], list):
        out["ids"] = [out["ids"]]

    return out


_parsers_cache = None

def _load_parsers():
    global _parsers_cache
    if _parsers_cache is not None:
        return _parsers_cache

    parsers = []
    base = os.path.dirname(__file__)
    pars_dir = os.path.join(base, "parsers")

    for fname in os.listdir(pars_dir):
        if fname.endswith(".py") and not fname.startswith("_"):

            modname = fname[:-3]
            module = importlib.import_module(f"log_parser.parsers.{modname}")

            for attr in dir(module):
                obj = getattr(module, attr)
                import typing

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

    _parsers_cache = parsers
    return parsers

def parse_line(line: str):
    line = line.rstrip("\n")
    parsers = _load_parsers()

    for parser in parsers:
        try:
            if parser.match(line):
                parsed = parser.parse(line)
                return normalize(parsed)
        except Exception as e:
            return normalize({
                "format": "parser_error",
                "raw": line,
                "level": "ERROR",
                "message": f"Parser crashed: {e}",
            })

    return normalize(fallback_parse(line))


def parse_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield parse_line(line)


def get_errors(log_stream):
    for log in log_stream:
        lvl = log.get("level", "N")
        if lvl in ("ERROR", "FATAL", "CRITICAL"):
            yield log
