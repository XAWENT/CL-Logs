"""
Kubernetes (k8s) logs parser.
Format: stdout/stderr from k8s pods - usually docker/json format
Also supports klog (Kubernetes logging)
"""
import re
import json
from typing import Dict, Any


class KubernetesParser:
    """Parser for Kubernetes pod logs."""
    
    # Klog format: I0115 10:30:45.123456    1 file.go:123] message
    _klog_pattern = re.compile(
        r"^([A-Z])\d{4}\s+(\d{2}:\d{2}:\d{2}\.\d+)\s+"
        r"(\d+)\s+([\w\.]+):(\d+)\]\s*(.*)$"
    )
    
    # Structured log format (JSON)
    _json_keys = ["ts", "level", "msg", "logger", "caller"]
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        
        # Check for klog format
        if re.match(r"^[IWDVE]\d{4}\s+\d{2}:\d{2}:\d{2}", stripped):
            return True
        
        # Check for JSON structured log
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
                # Check if it has k8s specific fields
                if any(k in data for k in self._json_keys) or "pod" in data or "namespace" in data:
                    return True
            except json.JSONDecodeError:
                pass
        
        return False
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try klog format first
        m = self._klog_pattern.match(raw)
        if m:
            level_char, time, pid, file, line_num, message = m.groups()
            
            level_map = {
                "I": "INFO",
                "W": "WARN", 
                "D": "DEBUG",
                "V": "DEBUG",
                "E": "ERROR"
            }
            level = level_map.get(level_char, "INFO")
            
            return {
                "format": "k8s_klog",
                "raw": raw,
                "date": "N",
                "time": time,
                "timestamp": "N",
                "level": level,
                "source": file,
                "module": "N",
                "thread": pid,
                "ids": [],
                "message": message,
                "file": file,
                "line": line_num
            }
        
        # Try JSON format
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
                
                # Extract timestamp
                timestamp = data.get("ts", data.get("timestamp", "N"))
                if timestamp != "N":
                    # k8s uses nanoseconds since epoch
                    if isinstance(timestamp, (int, float)):
                        date_part = "N"
                        time_part = "N"
                    else:
                        if "T" in str(timestamp):
                            date_part = str(timestamp).split("T")[0]
                            time_part = str(timestamp).split("T")[1]
                        else:
                            date_part = "N"
                            time_part = str(timestamp)
                else:
                    date_part = "N"
                    time_part = "N"
                
                # Extract level
                level = str(data.get("level", "INFO")).upper()
                level_map = {"I": "INFO", "W": "WARN", "D": "DEBUG", "E": "ERROR", "F": "CRITICAL"}
                level = level_map.get(level, level)
                
                # Extract message
                message = data.get("msg", data.get("message", raw))
                
                # Source info
                source = data.get("logger", data.get("pod", data.get("source", "k8s")))
                caller = data.get("caller", "N")
                
                return {
                    "format": "k8s_json",
                    "raw": raw,
                    "date": date_part,
                    "time": time_part,
                    "timestamp": str(timestamp),
                    "level": level,
                    "source": source,
                    "module": caller,
                    "thread": "N",
                    "ids": [],
                    "message": message,
                    "namespace": data.get("namespace", "N"),
                    "pod": data.get("pod", "N"),
                    "container": data.get("container", "N")
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback
        return {
            "format": "k8s",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "k8s",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
