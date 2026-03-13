"""
Apache HTTP Server error log parser.
Format: [day month dd hh:mm:ss.ccccce yyyy] [level] [pid tid] [client ip] message
"""
import re
from typing import Dict, Any


class ApacheErrorParser:
    """Parser for Apache HTTP Server error logs."""
    
    # Apache error log format
    _pattern = re.compile(
        r"^\[([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\d{4})\]\s+"  # timestamp
        r"\[(\w+)\]\s+"  # level: error, warn, info, debug, emerg, alert, crit, notice
        r"(?:\[pid\s+(\d+)\]\s+)?"  # optional pid
        r"(?:\[tid\s+(\d+)\]\s+)?"  # optional tid
        r"(?:\[client\s+([\d\.]+)(?::(\d+))?\]\s+)?"  # optional client IP:port
        r"(.*)$"  # message
    )
    
    # Apache 2.4+ with request
    _request_pattern = re.compile(
        r"^\[([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\d{4})\]\s+"
        r"\[(\w+)\]\s+"
        r"(?:\[pid\s+(\d+)\](?:\s+\[tid\s+(\d+)\])?\s+)?"
        r"(?:\[client\s+([\d\.]+)(?::(\d+))?\]\s+)?"
        r"\[uri\s+([^\]]+)\]\s*"  # request URI
        r"(.*)$"
    )
    
    # Simple format (no client)
    _simple_pattern = re.compile(
        r"^\[([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\d{4})\]\s+"
        r"\[(\w+)\]\s+(.*)$"
    )
    
    MONTHS = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        # Check for Apache error log format: [Mon Mon dd hh:mm:ss yyyy]
        return bool(re.match(r"^\[[A-Z][a-z]{2}\s+[A-Z][a-z]{2}", stripped))
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try request pattern first
        m = self._request_pattern.match(raw)
        if m:
            timestamp, level, pid, tid, client_ip, client_port, uri, message = m.groups()
            return self._build_result(timestamp, level, message, pid, tid, client_ip, client_port, uri)
        
        # Try main pattern
        m = self._pattern.match(raw)
        if m:
            timestamp, level, pid, tid, client_ip, client_port, message = m.groups()
            return self._build_result(timestamp, level, message, pid, tid, client_ip, client_port, None)
        
        # Try simple pattern
        m = self._simple_pattern.match(raw)
        if m:
            timestamp, level, message = m.groups()
            return self._build_result(timestamp, level, message, None, None, None, None, None)
        
        # Fallback
        return {
            "format": "apache_error",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "apache",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, timestamp: str, level: str, message: str,
                     pid: str, tid: str, client_ip: str, client_port: str,
                     uri: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse timestamp: "Mon Mon dd hh:mm:ss.cccccc yyyy"
        # e.g., "Mon Jan 15 10:30:45.123456 2024"
        parts = timestamp.split()
        if len(parts) >= 5:
            # Month is at position 1 (after day name)
            month = self.MONTHS.get(parts[1], "01")
            day = parts[2].zfill(2)
            year = parts[4]
            time_part = parts[3].split(".")[0]  # Remove microseconds
            date_part = f"{year}-{month}-{day}"
        else:
            date_part = "N"
            time_part = "N"
        
        # Map Apache level
        level = level.upper()
        level_map = {
            "EMERG": "CRITICAL",
            "ALERT": "CRITICAL", 
            "CRIT": "CRITICAL",
            "ERROR": "ERROR",
            "WARN": "WARN",
            "NOTICE": "INFO",
            "INFO": "INFO",
            "DEBUG": "DEBUG"
        }
        level = level_map.get(level, level)
        
        result = {
            "format": "apache_error",
            "raw": message if isinstance(message, str) else raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": "apache",
            "module": "N",
            "thread": tid if tid else "N",
            "ids": [],
            "message": message
        }
        
        if pid:
            result["pid"] = pid
        if client_ip:
            result["client_ip"] = client_ip
            result["client_port"] = client_port
        if uri:
            result["uri"] = uri
        
        return result
