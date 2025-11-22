from __future__ import annotations
import importlib
import pkgutil
from typing import Any, Dict, List

from . import fallback

_PARSERS = None


def _load_parsers():
    """
    Автоматически находит все модули в log_parser/parsers/
    и инициализирует все классы вида:

        class SomethingParser:
            def match(...)
            def parse(...)

    """
    global _PARSERS
    if _PARSERS is not None:
        return _PARSERS

    _PARSERS = []

    # ВАЖНО: правильное имя пакета
    pkg = __package__ + ".parsers"

    # загружаем модуль пакета parsers
    module = importlib.import_module(pkg)

    # итерируемся по файлам в папке parsers/
    for _, modname, _ in pkgutil.iter_modules(module.__path__):
        full_module_name = f"{pkg}.{modname}"
        mod = importlib.import_module(full_module_name)

        # ищем классы, которые выглядят как парсеры
        for name in dir(mod):
            obj = getattr(mod, name)
            if hasattr(obj, "match") and hasattr(obj, "parse") and callable(obj):
                try:
                    _PARSERS.append(obj())  # создаём экземпляр класса
                except Exception:
                    pass

    return _PARSERS


def parse_line(line: str) -> Dict[str, Any]:
    parsers = _load_parsers()

    # пробуем плагины
    for parser in parsers:
        try:
            if parser.match(line):
                return parser.parse(line)
        except Exception:
            pass

    # если никто не справился → fallback
    return fallback.fallback_parse(line)


def parse_file(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            out.append(parse_line(line))
    return out


def get_errors(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for e in logs:
        lvl = (e.get("level") or "").upper()

        # уровни ошибок
        if lvl in ("ERROR", "WARN", "FATAL", "CRITICAL"):
            output.append(e)
            continue

        # HTTP коды
        if e.get("status_code", 0) >= 500:
            output.append(e)
            continue

        # слова в сообщении
        msg = (e.get("message") or "").lower()
        if any(w in msg for w in ["exception", "traceback", "fatal", "panic"]):
            output.append(e)
            continue

    return output