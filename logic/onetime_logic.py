from log_parser import parse_file

def iter_log_entries(path: str, dangers: dict):
    for i, parsed in enumerate(parse_file(path), start=1):
        level = parsed["level"].strip().upper()
        is_danger = dangers.get(level, False)

        yield {
            "index": i,
            "level": level,
            "is_danger": is_danger,
            "raw": parsed["raw"],
            "format": parsed["format"],
            "date": parsed["date"],
            "time": parsed["time"],
            "message": parsed["message"],
            "source": parsed["source"],
        }


def analyze_log(path: str, dangers: dict):
    entries = list(iter_log_entries(path, dangers))
    return entries, [entry["index"] for entry in entries if entry["is_danger"]]
