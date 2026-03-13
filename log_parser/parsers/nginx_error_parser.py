"""
Nginx error log parser.
Format: year/monthonth/day hh:mm:ss [level] message
"""
import re
from typing import Dict, Any


class NginxErrorParser:
    """Parser for Nginx error logs."""
    
    # Nginx error log format
    _pattern = re.compile(
        r"^(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"  # timestamp
        r"\[(\w+)\]\s+"  # level: debug, info, notice, warn, error, crit, alert, emerg
        r"(?:(\d+)#(\d+):\s+)?"  # optional: pid#tid
        r"(.*)$"  # message
    )
    
    # With client IP
    _client_pattern = re.compile(
        r"^(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"\[(\w+)\]\s+"
        r"(?:(\d+)#(\d+):\s+)?"
        r"(?:(\d+\.\d+\.\d+\.\d+):?(\d+)?\s+-)?"
        r"(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        # Check for nginx timestamp format: YYYY/MM/DD HH:MM:SS
        return bool(re.match(r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}", stripped))
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try client pattern first
        m = self._client_pattern.match(raw)
        if m:
            timestamp, level, pid, tid, client_ip, client_port, message = m.groups()
            
            return self._build_result(timestamp, level, message, pid, tid, client_ip, client_port)
        
        # Try main pattern
        m = self._pattern.match(raw)
        if m:
            timestamp, level, pid, tid, message = m.groups()
            
            return self._build_result(timestamp, level, message, pid, tid, None, None)
        
        # Fallback
        return {
            "format": "nginx_error",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "nginx",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _build_result(self, timestamp: str, level: str, message: str,
                     pid: str, tid: str, client_ip: str, client_port: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse timestamp: YYYY/MM/DD HH:MM:SS
        date_part = timestamp.replace("/", "-").split()[0]
        time_part = timestamp.split()[1]
        
        # Map nginx level to standard
        level = level.upper()
        if level == "ERR":
            level = "ERROR"
        elif level in ("CRIT", "ALERT", "EMERG"):
            level = "CRITICAL"
        
        result = {
            "format": "nginx_error",
            "raw": message,
            "date": date_part,
            "time": time_part,
            "timestamp": f"{date_part}T{time_part}",
            "level": level,
            "source": "nginx",
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
        
        return result
