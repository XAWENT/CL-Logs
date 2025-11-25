import sys
import os

# Фикс пути — чтобы realtimeparser точно нашёл parser_engine
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE)

from realtimeparser import follow

# === ВВЕДИ СВОЙ ПУТЬ К ЛОГУ ТУТ ===
path = r"C:\Users\Тимофей\AppData\Roaming\.minecraft\logs\latest.log"

for parsed in follow(path):
    print(parsed)

