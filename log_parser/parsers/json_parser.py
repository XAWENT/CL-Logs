from __future__ import annotations
import json
from typing import Any, Dict

class JSONParser:
    def match(self, line: str) -> bool:
        text = line.strip()
        return text.startswith("{") and text.endswith("}")

    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        data = json.loads(raw)

        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")

        return {
            "format": "json",
            "raw": raw,

            "date": data.get("date", "N"),
            "time": data.get("time", "N"),
            "timestamp": data.get("timestamp", "N"),

            "level": data.get("level", "N"),
            "source": data.get("source", "json"),
            "module": data.get("module", "N"),
            "thread": data.get("thread", "N"),

            "ids": data.get("ids", []),
            "message": data.get("message", raw),

            **data
        }
