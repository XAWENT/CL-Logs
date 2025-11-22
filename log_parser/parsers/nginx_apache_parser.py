"""Parser for Nginx/Apache combined log format.

This parser recognizes the common log format emitted by web servers
like Nginx and Apache. The expected format is roughly:

```
<ip> <ident> <user> [<timestamp>] "<method> <path> <protocol>" <status> <size> "<referer>" "<user_agent>"
```

The parser extracts all the standard fields and returns a dictionary
with keys such as ``remote_ip``, ``timestamp_raw``, ``method``,
``path``, ``protocol``, ``status_code``, ``response_size``, ``referer``
and ``user_agent``. The resulting entry will have ``format`` set to
``"nginx_apache"``.
"""

from __future__ import annotations

import re
from typing import Any, Dict


class NginxApacheParser:
    """Parse Nginx/Apache combined log entries."""

    # Combined log pattern with optional referer and user agent
    _pattern = re.compile(
        r"(\S+) (\S+) (\S+) \[([^\]]+)\] "
        r"\"(\S+) ([^\"]+) (\S+)\" "  # method, path, protocol in quotes
        r"(\d{3}) (\d+|-)"  # status, size
        r"(?: \"([^\"]*)\" \"([^\"]*)\")?"  # optional referer and agent
    )

    def match(self, line: str) -> bool:
        # quick check: starts with an IPv4 address
        return bool(re.match(r"\d+\.\d+\.\d+\.\d+ ", line))

    def parse(self, line: str) -> Dict[str, Any]:
        m = self._pattern.fullmatch(line.strip())
        if not m:
            raise ValueError("Not a valid Nginx/Apache combined log line")
        (
            ip,
            ident,
            user,
            time_str,
            method,
            path,
            protocol,
            status,
            size,
            referer,
            user_agent,
        ) = m.groups()
        result = {
            "format": "nginx_apache",
            "remote_ip": ip,
            "user_ident": ident if ident != "-" else None,
            "user": user if user != "-" else None,
            "timestamp_raw": time_str,
            "method": method,
            "path": path,
            "protocol": protocol,
            "status_code": int(status),
            "response_size": int(size) if size != "-" else 0,
            "referer": referer,
            "user_agent": user_agent,
            "raw": line.strip(),
        }
        return result