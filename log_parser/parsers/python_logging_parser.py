"""
Python logging module parser.
Standard format: 2024-01-15 10:30:45,123 - module.name - LEVEL - Message
"""
import re
from typing import Dict, Any


class PythonLoggingParser:
    """Parser for Python logging module output."""
    
    # Standard Python logging format
    _pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+-\s+"  # timestamp
        r"([\w\.]+)\s+-\s+"  # logger name
        r"([A-Z]+)\s+-\s+"   # level
        r"(.*)$"             # message
    )
    
    # Simple format without logger name
    _simple_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3}))\s+-\s+"
        r"([A-Z]+)\s+-\s+(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        # Check for Python logging pattern
        return bool(self._pattern.match(stripped) or self._simple_pattern.match(stripped))
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try full pattern first
        m = self._pattern.match(raw)
        if m:
            timestamp, logger, level, message = m.groups()
            
            # Parse timestamp
            if "," in timestamp:
                date_part, time_part = timestamp.split()
                time_part = time_part.replace(",", ".")
            else:
                date_part, time_part = timestamp.split()
            
            return {
                "format": "python_logging",
                "raw": raw,
                "date": date_part,
                "time": time_part,
                "timestamp": timestamp.replace(" ", "T"),
                "level": level,
                "source": logger,
                "module": logger.rsplit(".", 1)[-1] if "." in logger else logger,
                "thread": "N",
                "ids": [],
                "message": message
            }
        
        # Try simple pattern
        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            
            if "," in timestamp:
                date_part, time_part = timestamp.split()
                time_part = time_part.replace(",", ".")
            else:
                date_part, time_part = timestamp.split()
            
            return {
                "format": "python_logging",
                "raw": raw,
                "date": date_part,
                "time": time_part,
                "timestamp": timestamp.replace(" ", "T"),
                "level": level,
                "source": "python",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": message
            }
        
        # Fallback
        return {
            "format": "python_logging",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "python",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
