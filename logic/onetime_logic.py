from log_parser import parse_file

def analyze_log(path: str, dangers: dict):

    parsedlogs = list(parse_file(path))
    entries = []
    danger_lines = []

    for i, parsed in enumerate(parsedlogs, start=1):
        level = parsed["level"].strip().upper()
        is_danger = dangers.get(level, False)

        entry = {
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

        if is_danger:
            danger_lines.append(i)

        entries.append(entry)

    return entries, danger_lines
