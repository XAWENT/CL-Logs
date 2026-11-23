"""
Docker container logs parser.
Format: timestamp container_name message
Or JSON format from docker log driver
"""
import re
import json
from typing import Dict, Any


class DockerParser:
    """Parser for Docker container logs."""

    # The json-file envelope and stream marker take precedence over JSON metadata.
    priority = 10
    
    # Standard docker timestamp format: 2024-01-15T10:30:45.123456789Z
    _pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"  # timestamp
        r"(?:container=(?P<name>[\w.-]+)\s+|(?P<id>[0-9a-f]{12}(?:[0-9a-f]{52})?)\s+|"
        r"(?P<compose_name>[\w.-]+)\s+\|\s*)"  # explicit container name/id
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
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                return False
            return (
                isinstance(data.get("log"), str)
                and data.get("stream") in ("stdout", "stderr")
                and isinstance(data.get("time"), str)
            )
        return bool(self._stream_pattern.match(stripped) or self._pattern.match(stripped))
    
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
            timestamp, name, container_id, compose_name, message = m.groups()
            container = name or container_id or compose_name
            
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
        date_part, separator, time_part = str(timestamp).partition("T")
        if separator:
            time_part = time_part.rstrip("Z")
        else:
            date_part = time_part = "N"
        
        # Stream type
        stream = data.get("stream", "N")
        level = "ERROR" if stream == "stderr" else self._detect_level(log)
        
        container = data.get("container")
        source = container.get("name", "docker") if isinstance(container, dict) else container or "docker"

        return {
            "format": "docker_json",
            "raw": raw,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": source,
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
