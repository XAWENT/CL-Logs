"""
AWS CloudWatch Logs parser.
Format: timestamp level message (with AWS specific fields)
"""
import re
import json
from typing import Dict, Any


class AWSCloudWatchParser:
    """Parser for AWS CloudWatch Logs."""
    
    # CloudWatch embedded metric format
    _embedded_pattern = re.compile(
        r"^\{.*\"@timestamp\".*\}$"
    )
    
    # Standard CloudWatch: 2024-01-15T10:30:45.123Z message
    _timestamp_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(.*)$"
    )
    
    # AWS service specific patterns
    _lambda_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+"
        r"(\w+)\s+"  # request ID
        r"(\w+)\s+"  # level
        r"(.*)$"
    )
    
    def match(self, line: str) -> bool:
        stripped = line.strip()
        
        # Check for JSON format (embedded metrics)
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
                # Check for CloudWatch fields
                if "@timestamp" in data or "timestamp" in data or "time" in data:
                    return True
            except json.JSONDecodeError:
                pass
        
        # Check for timestamp format
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", stripped):
            return True
        
        return False
    
    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        
        # Try embedded JSON format first
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
                return self._parse_json_format(data, raw)
            except json.JSONDecodeError:
                pass
        
        # Try Lambda format
        m = self._lambda_pattern.match(raw)
        if m:
            timestamp, request_id, level, message = m.groups()
            
            return self._build_result(timestamp, level, message, "lambda", request_id)
        
        # Try standard timestamp format
        m = self._timestamp_pattern.match(raw)
        if m:
            timestamp, message = m.groups()
            
            # Detect level from message
            level = self._detect_level(message)
            
            return self._build_result(timestamp, level, message, "cloudwatch", "N")
        
        # Fallback
        return {
            "format": "aws_cloudwatch",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": "N",
            "level": "N",
            "source": "aws",
            "module": "N",
            "thread": "N",
            "ids": [],
            "message": raw
        }
    
    def _parse_json_format(self, data: Dict, raw: str) -> Dict[str, Any]:
        """Parse JSON format from CloudWatch."""
        # Get timestamp
        timestamp = data.get("@timestamp", data.get("timestamp", data.get("time", "N")))
        
        # Parse timestamp
        if timestamp != "N" and "T" in str(timestamp):
            ts_str = str(timestamp)
            date_part = ts_str.split("T")[0]
            time_part = ts_str.split("T")[1].rstrip("Z")
        else:
            date_part = "N"
            time_part = "N"
        
        # Get level
        level = str(data.get("level", data.get("severity", "INFO"))).upper()
        if level in ("I", "INFO"):
            level = "INFO"
        elif level in ("W", "WARN", "WARNING"):
            level = "WARN"
        elif level in ("E", "ERROR"):
            level = "ERROR"
        elif level in ("D", "DEBUG"):
            level = "DEBUG"
        
        # Get message
        message = data.get("message", data.get("msg", raw))
        
        # Get source
        source = data.get("source", data.get("service", "aws"))
        
        # Extract AWS-specific fields
        result = {
            "format": "aws_cloudwatch_json",
            "raw": message if isinstance(message, str) else raw,
            "date": date_part,
            "time": time_part,
            "timestamp": str(timestamp),
            "level": level,
            "source": source,
            "module": data.get("function_name", "N"),
            "thread": data.get("request_id", "N"),
            "ids": [],
            "message": message
        }
        
        # Add AWS-specific fields
        if "request_id" in data:
            result["request_id"] = data["request_id"]
        if "function_name" in data:
            result["function_name"] = data["function_name"]
        if "log_group" in data:
            result["log_group"] = data["log_group"]
        
        return result
    
    def _build_result(self, timestamp: str, level: str, message: str,
                     source: str, request_id: str) -> Dict[str, Any]:
        """Build standardized result."""
        # Parse timestamp
        if "T" in timestamp:
            date_part = timestamp.split("T")[0]
            time_part = timestamp.split("T")[1].rstrip("Z")
        else:
            date_part = "N"
            time_part = timestamp
        
        return {
            "format": "aws_cloudwatch",
            "raw": message,
            "date": date_part,
            "time": time_part,
            "timestamp": timestamp,
            "level": level,
            "source": source,
            "module": "N",
            "thread": request_id,
            "ids": [],
            "message": message,
            "request_id": request_id
        }
    
    def _detect_level(self, message: str) -> str:
        """Detect log level from message content."""
        msg_upper = message.upper()
        if "ERROR" in msg_upper or "EXCEPTION" in msg_upper:
            return "ERROR"
        elif "WARN" in msg_upper:
            return "WARN"
        elif "DEBUG" in msg_upper:
            return "DEBUG"
        return "INFO"
