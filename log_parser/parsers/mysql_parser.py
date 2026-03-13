"""
MySQL/MariaDB database logs parser.
Supports: error log, slow query log, general log
"""
import re
from typing import Dict, Any


class MySQLParser:
    """Parser for MySQL/MariaDB database logs."""
    
    # MySQL error log format: YYYY-MM-DDTHH:MM:SS.ssssss [Note/Error/Warning] message
    _error_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]?\d*)\s+"  # timestamp
        r"\[(\w+)\]\s+"  # level: Note, Error, Warning
        r"(?:(\d+)\s+)?"  # optional thread ID
        r"(.*)$"  # message
    )
    
    # MySQL 8.0+ format
    _error_v8_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[ZT+-]*)\s+"  # timestamp
        r"(\d+)\s+"  # thread ID
        r"(\w+)\s+"  # level
        r"\[(\w+)\]\s+"  # subsystem
        r"(.*)$"  # message
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
        
        # Check for MySQL timestamp format
        return bool(
            re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", stripped) or
            re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", stripped)
        )
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try v8 format first
        m = self._error_v8_pattern.match(raw)
        if m:
            timestamp, thread_id, level, subsystem, message = m.groups()
            return self._build_result(timestamp, level, message, thread_id, subsystem)
        
        # Try MariaDB format
        m = self._mariadb_pattern.match(raw)
        if m:
            timestamp, level, thread_id, source, message = m.groups()
            return self._build_result(timestamp, level, message, thread_id, source)
        
        # Try main error pattern
        m = self._error_pattern.match(raw)
        if m:
            timestamp, level, thread_id, message = m.groups()
            return self._build_result(timestamp, level, message, thread_id, "N")
        
        # Try simple pattern
        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            return self._build_result(timestamp, level, message, None, "N")
        
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
    
    def _build_result(self, timestamp: str, level: str, message: str,
                     thread_id: str, subsystem: str) -> Dict[str, Any]:
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
            "INFORMATIONAL": "INFO"
        }
        level = level_map.get(level, level)
        
        result = {
            "format": "mysql",
            "raw": message if isinstance(message, str) else raw,
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
