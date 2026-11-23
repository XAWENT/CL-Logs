from log_parser import parse_file


def analyze_entries(parsed_entries, dangers):
    for index, parsed in enumerate(parsed_entries, start=1):
        level = parsed["level"]
        yield {
            "index": index,
            "level": level,
            "is_danger": dangers.get(level, False),
            "raw": parsed["raw"],
            "format": parsed["format"],
            "date": parsed["date"],
            "time": parsed["time"],
            "message": parsed["message"],
            "source": parsed["source"],
        }


def iter_log_entries(path: str, dangers: dict):
    yield from analyze_entries(parse_file(path), dangers)


def analyze_log(path: str, dangers: dict):
    entries = list(iter_log_entries(path, dangers))
    return entries, [entry["index"] for entry in entries if entry["is_danger"]]
