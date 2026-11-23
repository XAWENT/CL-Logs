from realtimeparser import start_mc_realtime


def iterate_realtime(path: str, dangers: dict, stop_event=None):
    i = 1
    for parsed in start_mc_realtime(path, stop_event):

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
