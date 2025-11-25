import time
import os
from log_parser import parse_line

def follow(path):
    path = os.path.abspath(path)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()

            if line:
                yield line.rstrip("\n")
            else:
                time.sleep(0.1)


def start_mc_realtime(path):
    for raw in follow(path):

        if not raw.strip():
            continue

        parsed = parse_line(raw)
        yield parsed  # КЛЮЧ: возвращаем наружу, НЕ print
