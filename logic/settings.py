import errno
import json
import os
from pathlib import Path
from stat import S_IMODE
from tempfile import NamedTemporaryFile

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
    dangers = default_dangers.copy()
    try:
        data = json.loads(Path(settings_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dangers
    if isinstance(data, dict):
        dangers.update({level: enabled for level, enabled in data.items() if isinstance(enabled, bool)})
    return dangers


def save_settings(dangers: dict):
    path = Path(settings_file).resolve()
    try:
        mode = S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = None
    if mode is not None and not os.access(path, os.W_OK):
        raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), settings_file)

    temp = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    temporary_path = Path(temp.name)
    try:
        with temp:
            json.dump(dangers, temp, indent=4, ensure_ascii=False)
        if mode is not None:
            temporary_path.chmod(mode)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)

def restoretodefaults():
    dangers = default_dangers.copy()
    save_settings(dangers)
    return dangers
