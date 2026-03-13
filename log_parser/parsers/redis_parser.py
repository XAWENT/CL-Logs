"""
Redis logs parser.
Format: timestamp level message (e.g., # Warning:...)  
"""
import re
from typing import Dict, Any


class RedisParser:
    """Parser for Redis server logs."""
    
    # Redis 7.x format: 1:M 15 Jan 2024 10:30:45.123 # message
    _pattern = re.compile(
        r"^(\d+):([A-Z]\w+)\s+"  # pid:role
        r"(\d+\s+\w+\s+\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"  # timestamp
        r"(\w+)\s+"  # level
        r"(.*)$"  # message
    )
    
    # Simple format: # Warning: ...
    _simple_pattern = re.compile(
        r"^(#)\s*(\w+):\s*(.*)$"
    )
    
    # Background save / spawn child
    _background_pattern = re.compile(
        r"^(\d+):(\w+)\s+(\d+\s+\w+\s+\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
        r"(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        return bool(
            stripped.startswith("#") or
            re.match(r"^\d+:[A-Z]", stripped) or
            re.match(r"^\d+:\s+\d+", stripped)
        )
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try main pattern
        m = self._pattern.match(raw)
        if m:
            pid, role, timestamp, level, message = m.groups()
            
            return self._build_result(timestamp, level, message, pid, role)
        
        # Try background pattern
        m = self._background_pattern.match(raw)
        if m:
            pid, role, timestamp, message = m.groups()
            
            return self._build_result(timestamp, "INFO", message, pid, role)
        
        # Try simple pattern
        m = self._simple_pattern.match(raw)
        if m:
            hash_mark, level, message = m.groups()
            
            return self._build_result("N", level, message, "N", "N")
        
        # Fallback
        return {
            "format": "redis",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "redis",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, timestamp: str, level: str, message: str,
                     pid: str, role: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse Redis timestamp: "15 Jan 2024 10:30:45.123"
        months = {
            "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
            "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
            "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
        }
        
        if timestamp != "N" and len(timestamp.split()) >= 3:
            parts = timestamp.split()
            if len(parts) >= 4:
                day = parts[0]
                month = months.get(parts[1], "01")
                year = parts[2]
                time_part = parts[3] if len(parts) > 3 else "N"
                date_part = f"{year}-{month}-{day}"
            else:
                date_part = "N"
                time_part = "N"
        else:
            date_part = "N"
            time_part = "N"
        
        # Map Redis level
        level = level.upper()
        if level in ("WARNING", "WARN"):
            level = "WARN"
        elif level == "ERR":
            level = "ERROR"
        
        return {
            "format": "redis",
            "raw": message if isinstance(message, str) else raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp if timestamp != "N" else "N",
            "level": level,
            "source": f"redis:{role}" if role != "N" else "redis",
            "module": role,
            "thread": pid,
            "ids": [],
            "message": message
        }
