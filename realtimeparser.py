import time
import os
from log_parser import parse_line


def follow(path):
    path = os.path.abspath(path)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()

            if line:  # новая строка появилась
                yield line.rstrip("\n")
            else:
                time.sleep(0.1)  # ждём, пока приложение что-то запишет


def start_mc_realtime(path):
    print(f"📡 Watching Minecraft logs: {path}\n")

    for raw in follow(path):

        # пропуск пустых/ненужных строк
        if not raw.strip():
            continue

        parsed = parse_line(raw)

        # вывод
        print("──────────── LOG ENTRY ────────────")
        print(f"RAW:    {parsed['raw']}")
        print(f"FORMAT: {parsed['format']}")
        print(f"LEVEL:  {parsed['level']}")

        # красивый TIME
        if parsed["date"] != "N":
            print(f"TIME:   {parsed['date']} {parsed['time']}")
        else:
            print(f"TIME:   {parsed['time']}")

        print(f"MESSAGE: {parsed['message']}")
        print(f"SOURCE:  {parsed['source']}\n")

        # алерты
        lvl = parsed["level"]
        if lvl in ("ERROR", "WARN", "FATAL", "CRITICAL"):
            print("🔥 DETECTED:", parsed)
            print("-----------------------------------\n")


if __name__ == "__main__":
    start_mc_realtime(
        r"C:\Users\Тимофей\AppData\Roaming\.minecraft\logs\latest.log"
    )
