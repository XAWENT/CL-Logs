"""
systemd journald logs parser.
Format: MMM DD hh:mm:ss hostname systemd[pid]: message
"""
import re
from typing import Dict, Any


class SystemdJournalParser:
    """Parser for systemd journald logs."""
    
    # systemd journal format
    _pattern = re.compile(
        r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"  # timestamp
        r"(\S+)\s+"  # hostname
        r"(\S+?)(?:\[(\d+)\])?:\s*"  # unit/process name and optional PID
        r"(.*)$"  # message
    )
    
    # With priority field
    _priority_pattern = re.compile(
        r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(\S+)\s+"
        r"(\S+?)(?:\[(\d+)\])?:\s*"
        r"\[([\w.]+)\]\s*"  # priority like PRIORITY=3
        r"(.*)$"
    )
    
    # Structured journal fields
    _structured_pattern = re.compile(
        r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(\S+)\s+"
        r"(\S+?)(?:\[(\d+)\])?:\s*"
        r"(\w+)=(\S+)\s+"  # KEY=VALUE
        r"(.*)$"
    )
    
    MONTHS = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }
    
    # Priority to level mapping
    PRIORITY_MAP = {
        "0": "EMERG",   # Emergency
        "1": "ALERT",   # Alert
        "2": "CRITICAL", # Critical
        "3": "ERROR",   # Error
        "4": "WARN",    # Warning
        "5": "NOTICE",  # Notice
        "6": "INFO",    # Informational
        "7": "DEBUG"    # Debug
    }
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        # Check for systemd format: "Mon DD HH:MM:SS hostname unit:"
        return bool(re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+", stripped))
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try priority pattern first
        m = self._priority_pattern.match(raw)
        if m:
            timestamp, hostname, unit, pid, priority, message = m.groups()
            level = self.PRIORITY_MAP.get(priority, "INFO")
            return self._build_result(timestamp, hostname, unit, pid, message, level, priority)
        
        # Try structured pattern
        m = self._structured_pattern.match(raw)
        if m:
            timestamp, hostname, unit, pid, key, value, message = m.groups()
            level = self._detect_level(message)
            return self._build_result(timestamp, hostname, unit, pid, message, level, None)
        
        # Try main pattern
        m = self._pattern.match(raw)
        if m:
            timestamp, hostname, unit, pid, message = m.groups()
            level = self._detect_level(message)
            return self._build_result(timestamp, hostname, unit, pid, message, level, None)
        
        # Fallback
        return {
            "format": "systemd",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "systemd",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, timestamp: str, hostname: str, unit: str, pid: str,
                     message: str, level: str, priority: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse timestamp: "Mon DD HH:MM:SS"
        parts = timestamp.split()
        if len(parts) >= 3:
            month = self.MONTHS.get(parts[0], "01")
            day = parts[1].zfill(2)
            time_part = parts[2]
            # Use current year as default
            import datetime
            year = datetime.datetime.now().year
            date_part = f"{year}-{month}-{day}"
        else:
            date_part = "N"
            time_part = "N"
        
        # Extract unit name (remove path if present)
        if "[" in unit:
            unit = unit.split("[")[0]
        
        result = {
            "format": "systemd",
            "raw": message if isinstance(message, str) else raw,
            "date": date_part,
            "time": time_part,
            "timestamp": f"{date_part}T{time_part}",
            "level": level,
            "source": unit,
            "module": "N",
            "thread": pid if pid else "N",
            "ids": [],
            "message": message
        }
        
        if hostname:
            result["hostname"] = hostname
        if priority:
            result["priority"] = priority
        
        return result
    
    def _detect_level(self, message: str) -> str:
        """Detect log level from message content."""
        msg_upper = message.upper()
        
        if any(kw in msg_upper for kw in ("EMERGENCY", "EMERG", "PANIC")):
            return "CRITICAL"
        elif "ALERT" in msg_upper:
            return "CRITICAL"
        elif any(kw in msg_upper for kw in ("CRITICAL", "CRIT", "FATAL")):
            return "CRITICAL"
        elif any(kw in msg_upper for kw in ("ERROR", "ERR", "FAILURE", "FAILED", "EXCEPTION")):
            return "ERROR"
        elif any(kw in msg_upper for kw in ("WARNING", "WARN", "WARNINGS")):
            return "WARN"
        elif "NOTICE" in msg_upper:
            return "INFO"
        elif "DEBUG" in msg_upper:
            return "DEBUG"
        
        return "INFO"
