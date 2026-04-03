import os
import json

settings_file = 'settings.json'

default_dangers = {
    "DEBUG": False,
    "TRACE": False,
    "WARN": True,
    "ERROR": True,
    "CRITICAL": True,
    "INFO": False,
    "NOTICE": False
}

def load_settings():
    if not os.path.exists(settings_file):
        return default_dangers.copy()

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = default_dangers.copy()
            merged.update(data)
            return merged
    except:
        return default_dangers.copy()


def save_settings(dangers: dict):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(dangers, f, indent=4, ensure_ascii=False)

def restoretodefaults():
    save_settings(default_dangers.copy())
    return default_dangers.copy()
