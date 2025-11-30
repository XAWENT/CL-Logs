from realtimeparser import start_mc_realtime

def iterate_realtime(path: str, dangers: dict):
    i = 1
    for parsed in start_mc_realtime(path):

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

        i += 1
