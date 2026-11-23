import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit


NOTIFICATION_CONFIG = Path("user_config.json")
NOTIFICATION_URL_ENV = "CL_LOGS_NOTIFICATION_URL"
NOTIFICATION_URL_REQUIRED = f"Укажите URL сервера уведомлений в {NOTIFICATION_URL_ENV}."


def notification_url():
    url = os.environ.get(NOTIFICATION_URL_ENV, "").strip()
    try:
        parts = urlsplit(url)
        port = parts.port
        if parts.scheme in ("http", "https") and parts.hostname and port != 0 and not (
            "?" in url or "#" in url or any(char.isspace() for char in url)
        ):
            return url.rstrip("/")
    except ValueError:
        pass
    return ""


def load_config(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", False

    if not isinstance(data, dict) or not isinstance(data.get("user_hash"), str):
        return "", False

    user_hash = data["user_hash"].strip()
    return user_hash, bool(user_hash) and data.get("notifications_enabled", True) is True


def save_config(path, user_hash, enabled):
    path = Path(path)
    data = {"user_hash": user_hash, "notifications_enabled": enabled}
    temp = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    temporary_path = Path(temp.name)
    try:
        with temp:
            json.dump(data, temp, indent=4, ensure_ascii=False)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
