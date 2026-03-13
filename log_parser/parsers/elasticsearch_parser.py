"""
Elasticsearch logs parser.
Format: [timestamp][level][class] message
"""
import re
from typing import Dict, Any


class ElasticsearchParser:
    """Parser for Elasticsearch logs."""
    
    # Main ES format: [2024-01-15T10:30:45,123][INFO ][class] message
    _pattern = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:,\d{3})?)\]"
        r"\[(\w+)\]"
        r"\[([\w\.\$]+)\]"
        r"\s*(.*)$"
    )
    
    _pattern_v8 = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\]"
        r"\[(\w+)\]"
        r"\[([\w\.\$]+)\]"
        r"\[([\w\.\/]+)\]"
        r"\s*(.*)$"
    )
    
    _gc_pattern = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{4})\]\s+"
        r"\[gc\]\s+(\w+)\s+(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        return bool(
            stripped.startswith("[") and 
            (self._pattern.match(stripped) or self._pattern_v8.match(stripped) or self._gc_pattern.match(stripped))
        )
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try v8 format first
        m = self._pattern_v8.match(raw)
        if m:
            timestamp, level, logger, action, message = m.groups()
            
            return self._build_result(timestamp, level, logger, message, "elasticsearch_v8", action)
        
        # Try main format
        m = self._pattern.match(raw)
        if m:
            timestamp, level, logger, message = m.groups()
            
            return self._build_result(timestamp, level, logger, message, "elasticsearch", "N")
        
        # Try GC format
        m = self._gc_pattern.match(raw)
        if m:
            timestamp, gc_type, message = m.groups()
            
            return self._build_result(timestamp, "INFO", "GC", message, "elasticsearch_gc", gc_type)
        
        # Fallback
        return {
            "format": "elasticsearch",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "elasticsearch",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, timestamp: str, level: str, logger: str, message: str, 
                      fmt: str, action: str) -> Dict[str, Any]:
        """Build standardized result dictionary."""
        # Parse timestamp
        if "T" in timestamp:
            if "," in timestamp:
                date_part = timestamp.split("T")[0]
                time_part = timestamp.split("T")[1].split(",")[0]
            else:
                date_part = timestamp.split("T")[0]
                time_part = timestamp.split("T")[1].rstrip("Z")
        else:
            date_part, time_part = "N", "N"
        
        # Map level
        level = level.upper()
        if level == "WARN":
            level = "WARN"
        
        return {
            "format": fmt,
            "raw": message if hasattr(message, '__iter__') and not isinstance(message, str) else message,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": logger,
            "module": action,
            "thread": "N",
            "ids": [],
            "message": message
        }
