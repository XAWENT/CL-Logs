"""Top-level package for the log parsing framework.

This package exposes a simple API for loading and using log parsers.
It dynamically discovers parser plugins in the :mod:`log_parser.parsers`
subpackage and falls back on generic heuristics when a line cannot
be handled by a specific plugin.

The primary entry points are:

* :func:`log_parser.parser_engine.parse_line` – parse a single log line.
* :func:`log_parser.parser_engine.parse_file` – parse an entire file.
* :func:`log_parser.parser_engine.get_errors` – filter out error-level entries.

Each parser plugin must define a class that implements two methods:

``match(self, line: str) -> bool``
    Return True if this parser can handle ``line``.

``parse(self, line: str) -> dict``
    Return a structured representation of ``line``.

The framework will call `match` in order on the list of registered
parsers. The first parser whose `match` returns True for a given line
gets to parse it. If none match, the generic fallback parser is
invoked to extract whatever information it can.

See the :mod:`log_parser.parsers` package for examples of built‑in
parsers, and :mod:`log_parser.fallback` for the heuristic fallback.

"""

from .parser_engine import parse_line, parse_file, get_errors  # noqa: F401