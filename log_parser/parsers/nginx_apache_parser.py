from __future__ import annotations
import re
from typing import Any, Dict

class NginxApacheParser:
    _pattern = re.compile(
        r"(\S+) (\S+) (\S+) \[([^\]]+)\] "
        r"\"(\S+) ([^\"]+) (\S+)\" "
        r"(\d{3}) (\d+|-)"
        r"(?: \"([^\"]*)\" \"([^\"]*)\")?"
    )

    def match(self, line: str) -> bool:
        return bool(re.match(r"\d+\.\d+\.\d+\.\d+ ", line))

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

        return {
            "format": "nginx_apache",
            "raw": raw,
            "date": "N",
            "time": "N",
            "timestamp": time_str,

            "level": "N",
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
            "status_code": int(status),
            "response_size": int(size) if size != "-" else 0,
            "referer": referer,
            "user_agent": user_agent,
        }
