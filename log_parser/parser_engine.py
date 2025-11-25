from __future__ import annotations
import os
import importlib
from log_parser.fallback import fallback_parse

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
                return parser.parse(line)
        except Exception:
            pass

    return fallback_parse(line)


def parse_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            out.append(parse_line(line))
    return out


def get_errors(logs):
    out = []
    for log in logs:
        lvl = log.get("level", "N")
        if lvl in ("ERROR", "FATAL", "CRITICAL"):
            out.append(log)
    return out
