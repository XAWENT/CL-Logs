"""Parser for JSON formatted log lines.

This parser attempts to parse any line that begins with ``{`` and
ends with ``}`` as JSON. If parsing succeeds it returns the parsed
object merged with some standard fields. If parsing fails, ``match``
returns False and the engine will try subsequent parsers.
"""

from __future__ import annotations

import json
from typing import Any, Dict


class JSONParser:
    """Parse structured JSON log entries.

    A line is considered a JSON entry if it appears to be a single
    JSON object delimited by ``{`` and ``}``. The parsed dict is
    augmented with a ``format`` field set to ``"json"`` and a
    ``raw`` field containing the original line.
    """

    def match(self, line: str) -> bool:
        # Quick heuristic: looks like a JSON object
        text = line.strip()
        return text.startswith("{") and text.endswith("}")

    def parse(self, line: str) -> Dict[str, Any]:
        data = json.loads(line)
        if not isinstance(data, dict):
            # only accept JSON objects
            raise ValueError("JSON root is not an object")
        # annotate the format
        data = dict(data)  # shallow copy
        data["format"] = "json"
        data["raw"] = line.strip()
        return data