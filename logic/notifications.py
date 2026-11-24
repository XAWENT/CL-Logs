import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import requests

from log_parser.redaction import mask_sensitive


NOTIFICATION_CONFIG = Path("user_config.json")
NOTIFICATION_URL_ENV = "CL_LOGS_NOTIFICATION_URL"
NOTIFICATION_URL_REQUIRED = f"Укажите URL сервера уведомлений в {NOTIFICATION_URL_ENV}."


class RecipientVerificationError(Exception):
    pass


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


def verify_notification_recipient(base_url, user_hash):
    if not base_url:
        raise RecipientVerificationError(NOTIFICATION_URL_REQUIRED)
    if len(user_hash) < 8:
        raise RecipientVerificationError("Хэш слишком короткий. Минимум 8 символов.")

    try:
        health_response = requests.get(f"{base_url}/", timeout=3)
        if not 200 <= health_response.status_code < 300:
            raise RecipientVerificationError("Сервер недоступен. Проверьте адрес сервера и соединение.")
        response = requests.post(f"{base_url}/send", json={
            "user_hash": user_hash,
            "message": "Проверка уведомлений CL-Logs",
            "level": "INFO",
        }, timeout=5)
    except requests.Timeout as exc:
        raise RecipientVerificationError("Таймаут при подключении к серверу.") from exc
    except requests.RequestException as exc:
        raise RecipientVerificationError("Не удалось подключиться к серверу.") from exc

    if response.status_code == 404:
        raise RecipientVerificationError("Получатель не найден. Проверьте user_hash.")
    if not 200 <= response.status_code < 300:
        raise RecipientVerificationError(f"Ошибка сервера: {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        return ""
    user = data.get("user") if isinstance(data, dict) else None
    name = user.get("first_name") if isinstance(user, dict) else None
    return name if isinstance(name, str) else ""


def send_log_notification(level, message, source, timestamp, user_hash):
    base_url = notification_url()
    if not base_url or not user_hash:
        return False

    try:
        level, message, source, timestamp = (
            mask_sensitive(value) for value in (level, message, source, timestamp)
        )
        response = requests.post(f"{base_url}/send", json={
            "user_hash": user_hash,
            "level": level,
            "message": f"⚠️ {level}\n📝 Сообщение: {message}".strip(),
        }, timeout=10)
        delivered = 200 <= response.status_code < 300
        if not delivered or level != "ERROR":
            return delivered

        response = requests.post(f"{base_url}/send_email", json={
            "user_hash": user_hash,
            "subject": f"🚨 КРИТИЧЕСКАЯ ОШИБКА - {timestamp}",
            "message": (
                "🚨 КРИТИЧЕСКАЯ ОШИБКА В СИСТЕМЕ\n\n"
                f"⏰ Время события: {timestamp}\n📁 Источник: {source}\n🔴 Уровень: {level}\n\n"
                f"📋 Сообщение ошибки:\n{message}\n\n"
                "⚠️ Требуется немедленное вмешательство!"
            ),
        }, timeout=10)
        return 200 <= response.status_code < 300
    except Exception:
        return False
