from __future__ import annotations
import re
from typing import Any, Dict

class NginxApacheParser:
    _pattern = re.compile(
        r"(\S+)\s+(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+"
        r"\"(\S+)\s+([^\"]+)\s+(HTTP/[\d.]+)\"\s+"
        r"(\d{3})\s+(\d+|-)"
        r"(?:\s+\"([^\"]*)\"\s+\"([^\"]*)\")?"
    )

    def match(self, line: str) -> bool:
        return bool(self._pattern.fullmatch(line.strip()))

    def parse(self, line: str) -> Dict[str, Any]:
        raw = line.strip()
        m = self._pattern.fullmatch(raw)
        if not m:
            return {
                "format": "nginx_apache",
                "raw": raw,
                "date": "N",
                "time": "N",
                "timestamp": "N",
                "level": "N",
                "source": "generic",
                "module": "N",
                "thread": "N",
                "ids": [],
                "message": raw
            }

        (
            ip, ident, user, time_str,
            method, path, protocol, status, size,
            referer, user_agent
        ) = m.groups()

        status_code = int(status)
        if status_code >= 500:
            level = "ERROR"
        elif status_code >= 400:
            level = "WARN"
        else:
            level = "INFO"

        return {
            "format": "nginx_apache",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": time_str,

            "level": level,
            "source": ip,
            "module": "N",
            "thread": "N",

            "ids": [],
            "message": f"{method} {path} {status}",

            "remote_ip": ip,
            "user_ident": ident,
            "user": user,
            "method": method,
            "path": path,
            "protocol": protocol,
            "status_code": status_code,
            "response_size": int(size) if size != "-" else 0,
            "referer": referer,
            "user_agent": user_agent,
        }
