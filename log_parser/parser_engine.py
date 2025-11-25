from __future__ import annotations
import os
import importlib
from log_parser.fallback import fallback_parse


# ============================
# Универсальная нормализация
# ============================

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

def normalize(parsed: dict):
    out = {}

    for key, default in STANDARD_FIELDS.items():
        out[key] = parsed.get(key, default)

    # приведение уровня
    out["level"] = str(out["level"]).upper()

    # ids должен быть списком
    if not isinstance(out["ids"], list):
        out["ids"] = [out["ids"]]

    return out


# ============================
# Загрузка плагинов (парсеров)
# ============================

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


# ============================
# Главная функция — парс строки
# ============================

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

    # fallback
    return normalize(fallback_parse(line))


# ============================
# Парс файла (стриминг)
# ============================

def parse_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield parse_line(line)


# ============================
# Фильтр ошибок
# ============================

def get_errors(log_stream):
    for log in log_stream:
        lvl = log.get("level", "N")
        if lvl in ("ERROR", "FATAL", "CRITICAL"):
            yield log
