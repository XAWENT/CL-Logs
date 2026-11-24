from __future__ import annotations
import json
import re
from typing import Any, Dict


_ISO_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
    r"(?:Z|[+-]\d{2}:?\d{2})?"
)


class JSONParser:
    priority = -100

    def match(self, line: str) -> bool:
        text = line.strip()
        return text.startswith("{") and text.endswith("}")

    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        data = json.loads(raw)

        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")

        timestamp = data.get("timestamp", "N")
        iso = _ISO_TIMESTAMP.fullmatch(timestamp) if isinstance(timestamp, str) else None
        date, time = iso.groups() if iso else ("N", "N")

        return {
            **data,
            "format": "json",
            "raw": raw,

            "date": data.get("date", date),
            "time": data.get("time", time),
            "timestamp": timestamp,

            "level": data.get("level", "N"),
            "source": data.get("source", "json"),
            "module": data.get("module", "N"),
            "thread": data.get("thread", "N"),

            "ids": data.get("ids", []),
            "message": data.get("message", raw),
        }
