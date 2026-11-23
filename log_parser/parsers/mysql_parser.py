"""
MySQL/MariaDB database logs parser.
Supports: error log, slow query log, general log
"""
import re
from typing import Dict, Any


class MySQLParser:
    """Parser for MySQL/MariaDB database logs."""

    _iso_timestamp = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
    _severity = r"Note|System|Info(?:rmational)?|Warning|Warn|Error|Fatal|Debug"
    
    # MySQL error log format: YYYY-MM-DDTHH:MM:SS.ssssss [Note/Error/Warning] message
    _error_pattern = re.compile(
        rf"^({_iso_timestamp})\s+"
        rf"\[({_severity})\]\s+"
        r"(?:(\d+)\s+)?"  # optional thread ID
        r"(.*)$",
        re.IGNORECASE,
    )
    
    # MySQL 8.0+ format
    _error_v8_pattern = re.compile(
        rf"^({_iso_timestamp})\s+"
        r"(\d+)\s+"  # thread ID
        rf"(?:\[({_severity})\]|({_severity}))\s+"
        r"(?:\[MY-\d+\]\s+)?"
        r"\[([\w.-]+)\]\s+"
        r"(.*)$",
        re.IGNORECASE,
    )

    _thread_note_pattern = re.compile(
        rf"^({_iso_timestamp})\s+(\d+)\s+\[(Note|Warning|Error)\]\s+(.*)$",
        re.IGNORECASE,
    )
    
    # Simple error format
    _simple_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"  # timestamp
        r"(\w+):\s+(.*)$"  # level: message
    )
    
    # MariaDB format
    _mariadb_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"  # timestamp
        r"\[(\w+)\]\s+"  # level
        r"(?:(\d+)\s+)?"  # thread ID
        r"(?:\d+\s+)?(\w+(?:\.\w+)?):\s+"  # source file
        r"(.*)$"  # message
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()

        if (
            self._error_v8_pattern.match(stripped)
            or self._thread_note_pattern.match(stripped)
            or self._mariadb_pattern.match(stripped)
        ):
            return True
        legacy = self._error_pattern.match(stripped)
        if legacy:
            return legacy.group(2).lower() == "note" or legacy.group(3) is not None
        simple = self._simple_pattern.match(stripped)
        return bool(simple and simple.group(2).lower() == "note")
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try v8 format first
        m = self._error_v8_pattern.match(raw)
        if m:
            timestamp, thread_id, bracketed_level, bare_level, subsystem, message = m.groups()
            return self._build_result(raw, timestamp, bracketed_level or bare_level, message, thread_id, subsystem)

        m = self._thread_note_pattern.match(raw)
        if m:
            timestamp, thread_id, level, message = m.groups()
            return self._build_result(raw, timestamp, level, message, thread_id, "N")
        
        # Try MariaDB format
        m = self._mariadb_pattern.match(raw)
        if m:
            timestamp, level, thread_id, source, message = m.groups()
            return self._build_result(raw, timestamp, level, message, thread_id, source)
        
        # Try main error pattern
        m = self._error_pattern.match(raw)
        if m:
            timestamp, level, thread_id, message = m.groups()
            return self._build_result(raw, timestamp, level, message, thread_id, "N")
        
        # Try simple pattern
        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            return self._build_result(raw, timestamp, level, message, None, "N")
        
        # Fallback
        return {
            "format": "mysql",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "mysql",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, raw: str, timestamp: str, level: str, message: str,
                     thread_id: str | None, subsystem: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse timestamp
        if "T" in timestamp:
            date_part = timestamp.split("T")[0]
            time_part = timestamp.split("T")[1].rstrip("Z+")
        else:
            parts = timestamp.split()
            date_part = parts[0] if len(parts) > 0 else "N"
            time_part = parts[1] if len(parts) > 1 else "N"
        
        # Map MySQL level
        level = level.upper()
        level_map = {
            "ERROR": "ERROR",
            "WARNING": "WARN",
            "WARN": "WARN",
            "NOTE": "INFO",
            "SYSTEM": "INFO",
            "INFORMATIONAL": "INFO"
        }
        level = level_map.get(level, level)
        
        result = {
            "format": "mysql",
            "raw": raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": subsystem if subsystem != "N" else "mysql",
            "module": subsystem,
            "thread": thread_id if thread_id else "N",
            "ids": [],
            "message": message
        }
        
        if thread_id:
            result["thread_id"] = thread_id
        if subsystem and subsystem != "N":
            result["subsystem"] = subsystem
        
        return result
