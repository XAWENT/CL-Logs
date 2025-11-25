import time
import os
from log_parser import parse_line

def follow(path):
    path = os.path.abspath(path)

    # открываем файл один раз
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        # ставим указатель в конец
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()

            if line:
                yield line.rstrip("\n")
            else:
                # нет строки — ждём, пока приложение что-то запишет
                time.sleep(0.1)

def start_mc_realtime(path):
    print(f"📡 Watching Minecraft logs: {path}\n")

    for raw in follow(path):
        if not raw.strip():
            continue

        parsed = parse_line(raw)

        print("RAW:", raw)
        print("PARSED:", parsed)

        lvl = str(parsed.get("level", "N")).upper()
        if lvl in ("ERROR", "WARN"):
            print("🔥 DETECTED:", parsed)

        print()


if __name__ == "__main__":
    start_mc_realtime(
        r"C:\Users\Тимофей\AppData\Roaming\.minecraft\logs\latest.log"
    )



