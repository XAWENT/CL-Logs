"""
PostgreSQL database logs parser.
Format: timestamp LOG/WARNING/ERROR/LOG: message
"""
import re
from typing import Dict, Any


class PostgreSQLParser:
    """Parser for PostgreSQL database logs."""
    
    # PostgreSQL main log format
    _pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\w+)\s+"  # timestamp
        r"\[(\d+)\]\s+"  # process ID
        r"(\w+):\s+"  # LOG/WARNING/ERROR/etc
        r"(.*)$"  # message
    )
    
    # Simple format without PID
    _simple_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
        r"(\w+):\s+(.*)$"
    )
    
    # PostgreSQL 15+ format with severity
    _modern_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\.\d+\s+\w+)\s+"
        r"\[(\d+)\]\s+"
        r"(\w+)\s+(\w+):\s+(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        return bool(
            self._pattern.match(stripped) or 
            self._simple_pattern.match(stripped) or
            self._modern_pattern.match(stripped)
        )
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try modern format first
        m = self._modern_pattern.match(raw)
        if m:
            timestamp, pid, severity, level, message = m.groups()
            
            # Map PostgreSQL severity to standard
            level = self._map_level(severity, level)
            
            return {
                "format": "postgresql_modern",
                "raw": raw,
                "date": timestamp.split()[0],
                "time": timestamp.split()[1],
                "timestamp": timestamp,
                "level": level,
                "source": "postgresql",
                "module": "N",
                "thread": pid,
                "ids": [],
                "message": message,
                "severity": severity,
                "pid": pid
            }
        
        # Try main format
        m = self._pattern.match(raw)
        if m:
            timestamp, pid, level, message = m.groups()
            
            # Map PostgreSQL level
            level = self._map_level(level, level)
            
            return {
                "format": "postgresql",
                "raw": raw,
                "date": timestamp.split()[0],
                "time": timestamp.split()[1] if len(timestamp.split()) > 1 else "N",
                "timestamp": timestamp,
                "level": level,
                "source": "postgresql",
                "module": "N",
                "thread": pid,
                "ids": [],
                "message": message,
                "pid": pid
            }
        
        # Try simple format
        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            
            return {
                "format": "postgresql_simple",
                "raw": raw,
                "date": timestamp.split()[0],
                "time": timestamp.split()[1] if len(timestamp.split()) > 1 else "N",
                "timestamp": timestamp,
                "level": self._map_level(level, level),
                "source": "postgresql",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": message
            }
        
        # Fallback
        return {
            "format": "postgresql",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "postgresql",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _map_level(self, pg_level: str, detail: str) -> str:
        """Map PostgreSQL log levels to standard levels."""
        pg_level = pg_level.upper()
        
        if pg_level in ("ERROR", "FATAL", "PANIC"):
            return "ERROR"
        elif pg_level in ("WARNING", "NOTICE", "INFO"):
            return "WARN"
        elif pg_level == "DEBUG":
            return "DEBUG"
        else:
            return "INFO"
