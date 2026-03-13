"""
Docker container logs parser.
Format: timestamp container_name message
Or JSON format from docker log driver
"""
import re
import json
from typing import Dict, Any, Optional


class DockerParser:
    """Parser for Docker container logs."""
    
    # Standard docker timestamp format: 2024-01-15T10:30:45.123456789Z
    _pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"  # timestamp
        r"([a-zA-Z0-9_\-\.]+)\s+"  # container name/id
        r"(.*)$"  # message
    )
    
    # Docker with stream type (stdout/stderr)
    _stream_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"
        r"(stdout|stderr)\s+"
        r"(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        # Check for docker timestamp format at start
        return bool(self._pattern.match(stripped) or self._stream_pattern.match(stripped))
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try stream pattern first
        m = self._stream_pattern.match(raw)
        if m:
            timestamp, stream, message = m.groups()
            level = "ERROR" if stream == "stderr" else "INFO"
            
            # Parse timestamp
            if "T" in timestamp:
                date_part = timestamp.split("T")[0]
                time_part = timestamp.split("T")[1].rstrip("Z")
            
            return {
                "format": "docker",
                "raw": raw,
                "date": date_part,
                "time": time_part,
                "timestamp": timestamp,
                "level": level,
                "source": "docker",
                "module": stream,
                "thread": "N",
                "ids": [],
                "message": message,
                "stream": stream
            }
        
        # Try standard pattern
        m = self._pattern.match(raw)
        if m:
            timestamp, container, message = m.groups()
            
            # Parse timestamp
            if "T" in timestamp:
                date_part = timestamp.split("T")[0]
                time_part = timestamp.split("T")[1].rstrip("Z")
            else:
                date_part, time_part = timestamp.split()
            
            # Detect level from message
            level = self._detect_level(message)
            
            return {
                "format": "docker",
                "raw": raw,
                "date": date_part,
                "time": time_part,
                "timestamp": timestamp,
                "level": level,
                "source": container,
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": message,
                "container": container
            }
        
        # Try JSON format (common with json-file log driver)
        if raw.startswith("{") and raw.endswith("}"):
            try:
                data = json.loads(raw)
                return self._parse_json_docker(data, raw)
            except json.JSONDecodeError:
                pass
        
        # Fallback
        return {
            "format": "docker",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "docker",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _parse_json_docker(self, data: Dict, raw: str) -> Dict[str, Any]:
        """Parse JSON format from Docker json-file log driver."""
        log = data.get("log", raw)
        timestamp = data.get("time", data.get("timestamp", "N"))
        
        # Parse timestamp
        if timestamp != "N" and "T" in timestamp:
            date_part = timestamp.split("T")[0]
            time_part = timestamp.split("T")[1].rstrip("Z")
        else:
            date_part = "N"
            time_part = "N"
        
        # Stream type
        stream = data.get("stream", "N")
        level = "ERROR" if stream == "stderr" else self._detect_level(log)
        
        return {
            "format": "docker_json",
            "raw": raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": data.get("container", {}).get("name", "docker"),
            "module": stream,
            "thread": "N",
            "ids": [],
            "message": log.strip(),
            "stream": stream
        }
    
    def _detect_level(self, message: str) -> str:
        """Detect log level from message content."""
        msg_upper = message.upper()
        if "ERROR" in msg_upper or "FATAL" in msg_upper:
            return "ERROR"
        elif "WARN" in msg_upper:
            return "WARN"
        elif "DEBUG" in msg_upper:
            return "DEBUG"
        elif "TRACE" in msg_upper:
            return "DEBUG"
        return "INFO"
