import sys

from menu import menu
from colors import C

from log_parser.redaction import MASK, mask_sensitive

from logic.notifications import (
    NOTIFICATION_CONFIG,
    NOTIFICATION_URL_REQUIRED,
    RecipientVerificationError,
    load_config,
    notification_url,
    save_config,
    send_log_notification,
    verify_notification_recipient,
)
from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime
from logic.settings import load_settings, save_settings, restoretodefaults


def check_notifications_status():
    user_hash, enabled = load_config(NOTIFICATION_CONFIG)
    return user_hash or None, enabled and bool(notification_url())


def save_notification_settings(user_hash, enabled):
    try:
        save_config(NOTIFICATION_CONFIG, user_hash, enabled)
    except OSError as e:
        print(C.R + f"❌ Не удалось сохранить настройки уведомлений: {e}" + C.RESET)
        return False
    return True


def setup_notifications(*, change_hash=False):
    print(C.C + "\n" + "═" * 50 + C.RESET)
    print(C.C + "         НАСТРОЙКА СИСТЕМЫ УВЕДОМЛЕНИЙ" + C.RESET)
    print(C.C + "═" * 50 + C.RESET + "\n")

    base_url = notification_url()
    saved_hash, enabled = load_config(NOTIFICATION_CONFIG)
    current_status = saved_hash or None, enabled and bool(base_url)
    if not base_url:
        print(C.Y + NOTIFICATION_URL_REQUIRED + C.RESET)
        return current_status

    recipient = ""
    if saved_hash and not change_hash:
        print(C.Y + f"📋 Найден сохраненный user_hash: {MASK}" + C.RESET)
        use_saved = input(C.Y + "Использовать его? (y/n): " + C.RESET).lower()
        if use_saved == "y":
            recipient = saved_hash

    while True:
        if not recipient:
            print(C.W + "📝 Для отправки уведомлений нужен ваш user_hash." + C.RESET)
            print(C.W + "   Его можно получить у администратора системы.\n" + C.RESET)
            recipient = input(C.Y + "Введите ваш user_hash (или Enter для пропуска): " + C.RESET).strip()
            if not recipient:
                return current_status

        print(C.C + "\n🔍 Проверяем соединение с сервером..." + C.RESET)
        try:
            name = verify_notification_recipient(base_url, recipient)
        except RecipientVerificationError as exc:
            print(C.R + f"❌ Ошибка: {exc}" + C.RESET)
            if input(C.Y + "🔄 Попробовать снова? (y/n): " + C.RESET).lower() != "y":
                return current_status
            recipient = ""
            continue

        if not save_notification_settings(recipient, True):
            return current_status
        print(C.G + "\n✅ Настройка завершена успешно!" + C.RESET)
        if name:
            print(C.C + f"👤 Пользователь: {name}" + C.RESET)
        return recipient, True


def send_notification(level, message, source, timestamp="", user_hash=None):
    return send_log_notification(level, message, source, timestamp, user_hash)


def main():
    if sys.stdin.isatty() and sys.stdout.isatty():
        from console_ui import LogConsole
        LogConsole(send_notification).run()
        return

    dangers = load_settings()

    user_hash, notifications_enabled = check_notifications_status()

    while True:
        choice = menu()
        truedangers = [lvl for lvl in dangers if dangers[lvl]]

        if choice == "1":
            path = input(C.Y + "📁 Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n" + "═" * 50 + C.RESET)
            print(C.C + "       РЕЖИМ РЕАЛЬНОГО ВРЕМЕНИ" + C.RESET)
            print(C.C + "═" * 50 + C.RESET + "\n")

            if not notification_url():
                print(C.Y + NOTIFICATION_URL_REQUIRED + C.RESET)
            elif not notifications_enabled:
                print(C.Y + "🔕 Уведомления отключены." + C.RESET)
                setup_now = input(C.Y + "⚙ Настроить уведомления сейчас? (y/n): " + C.RESET).lower()
                if setup_now == 'y':
                    user_hash, notifications_enabled = setup_notifications()
                    if notifications_enabled:
                        print(C.G + "\n✅ Уведомления включены!\n" + C.RESET)
                    else:
                        print(C.Y + "\n🔕 Уведомления остались отключенными.\n" + C.RESET)

            try:
                for entry in iterate_realtime(path, dangers):
                    if entry["level"] == "ERROR":
                        icon = "❌"
                        color = C.R
                    elif entry["level"] == "WARN":
                        icon = "⚠️"
                        color = C.Y
                    else:
                        icon = "ℹ️"
                        color = C.W if entry["is_danger"] else C.G

                    print(color + f"\n{icon} ЗАПИСЬ #{entry['index']}" + C.RESET)
                    print(color + "─" * 40 + C.RESET)

                    if entry["date"] != "N":
                        timestamp = f"{entry['date']} {entry['time']}"
                        print(f"📅 {timestamp}")
                    else:
                        timestamp = entry['time']
                        print(f"⏰ {timestamp}")

                    print(f"🔴 Уровень: {entry['level']}")
                    print(f"🔧 Источник: {entry['source']}")
                    print(f"💬 Сообщение: {entry['message']}")

                    if len(entry['raw']) > 100:
                        print(f"📄 RAW: {entry['raw'][:100]}..." + C.RESET)
                    else:
                        print(f"📄 RAW: {entry['raw']}" + C.RESET)

                    print(color + "─" * 40 + C.RESET)

                    if notifications_enabled and user_hash and entry["is_danger"]:
                        print(C.C + "📨 Отправка уведомления..." + C.RESET)
                        if send_notification(
                                level=entry["level"],
                                message=entry["message"],
                                source=entry["source"],
                                timestamp=timestamp,
                                user_hash=user_hash
                        ):
                            print(C.G + "✅ Уведомление отправлено" + C.RESET)
                        else:
                            print(C.Y + "⚠ Не удалось отправить уведомление" + C.RESET)
                        print()

            except FileNotFoundError:
                print(C.R + "\n❌ Файл не найден. Проверьте путь!" + C.RESET)
            except KeyboardInterrupt:
                print(C.Y + "\n\n⏹ Остановлено пользователем" + C.RESET)
            except Exception as e:
                print(C.R + "\n❌ Ошибка: " + mask_sensitive(str(e)) + C.RESET)

            input(C.Y + "\n⏎ Нажмите Enter, чтобы вернуться в меню..." + C.RESET)


        elif choice == "2":
            path = input(C.Y + "📁 Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n" + "═" * 50 + C.RESET)
            print(C.C + "          АНАЛИЗ ЛОГ-ФАЙЛА" + C.RESET)
            print(C.C + "═" * 50 + C.RESET + "\n")

            if not notification_url():
                print(C.Y + NOTIFICATION_URL_REQUIRED + C.RESET)
            elif not notifications_enabled:
                print(C.Y + "🔕 Уведомления отключены." + C.RESET)
                setup_now = input(C.Y + "⚙ Настроить уведомления сейчас? (y/n): " + C.RESET).lower()
                if setup_now == 'y':
                    user_hash, notifications_enabled = setup_notifications()
                    if notifications_enabled:
                        print(C.G + "\n✅ Уведомления включены!\n" + C.RESET)
                    else:
                        print(C.Y + "\n🔕 Уведомления остались отключенными.\n" + C.RESET)

            try:
                entries, danger_lines = analyze_log(path, dangers)
            except FileNotFoundError:
                print(C.R + "❌ Файл не найден. Проверьте путь!" + C.RESET)
                input(C.Y + "\n⏎ Нажмите Enter, чтобы продолжить..." + C.RESET)
                continue
            except Exception as e:
                print(C.R + "❌ Ошибка: " + mask_sensitive(str(e)) + C.RESET)
                input(C.Y + "\n⏎ Нажмите Enter, чтобы продолжить..." + C.RESET)
                continue

            error_count = 0
            warn_count = 0
            sent_count = 0

            for entry in entries:
                if entry["level"] == "ERROR":
                    icon = "❌"
                    color = C.R
                    error_count += 1
                elif entry["level"] == "WARN":
                    icon = "⚠️"
                    color = C.Y
                    warn_count += 1
                else:
                    icon = "ℹ️"
                    color = C.W if entry["is_danger"] else C.G

                print(color + f"\n{icon} ЗАПИСЬ #{entry['index']}" + C.RESET)
                print(color + "─" * 40 + C.RESET)

                if entry["date"] != "N":
                    timestamp = f"{entry['date']} {entry['time']}"
                    print(f"📅 {timestamp}")
                else:
                    timestamp = entry['time']
                    print(f"⏰ {timestamp}")

                print(f"🔴 Уровень: {entry['level']}")
                print(f"🔧 Источник: {entry['source']}")
                print(f"💬 Сообщение: {entry['message']}")
                print(f"📋 Формат: {entry['format']}")

                if len(entry['raw']) > 80:
                    print(f"📄 RAW: {entry['raw'][:80]}..." + C.RESET)
                else:
                    print(f"📄 RAW: {entry['raw']}" + C.RESET)

                print(color + "─" * 40 + C.RESET)

                if notifications_enabled and user_hash and entry["is_danger"]:
                    print(C.C + "📨 Отправка уведомления..." + C.RESET)
                    if send_notification(
                            level=entry["level"],
                            message=entry["message"],
                            source=entry["source"],
                            timestamp=timestamp,
                            user_hash=user_hash
                    ):
                        sent_count += 1
                        print(C.G + "✅ Уведомление отправлено" + C.RESET)
                    else:
                        print(C.Y + "⚠ Не удалось отправить уведомление" + C.RESET)
                    print()

            print(C.C + "\n" + "═" * 50 + C.RESET)
            print(C.C + "            СВОДКА АНАЛИЗА" + C.RESET)
            print(C.C + "═" * 50 + C.RESET + "\n")

            print(C.W + f"📊 Всего записей: {len(entries)}" + C.RESET)
            print(C.R + f"❌ Ошибок (ERROR): {error_count}" + C.RESET)
            print(C.Y + f"⚠️  Предупреждений (WARN): {warn_count}" + C.RESET)
            print(C.C + f"🚨 Нежелательных событий: {len(danger_lines)}" + C.RESET)

            if notifications_enabled and sent_count > 0:
                print(C.G + f"\n📨 Отправлено уведомлений: {sent_count}" + C.RESET)

            if danger_lines:
                print(C.R + f"\n📍 Строки с событиями: {', '.join(map(str, danger_lines))}" + C.RESET)

            input(C.Y + "\n⏎ Нажмите Enter, чтобы вернуться в меню..." + C.RESET)


        elif choice == "3":
            print(C.W + f"\n🔧 Текущие уровни опасности: {', '.join(truedangers)}" + C.RESET)

            if not notification_url():
                print(C.Y + "🔕 Уведомления: ВЫКЛ. " + NOTIFICATION_URL_REQUIRED + C.RESET)
            elif notifications_enabled and user_hash:
                print(C.G + f"🔔 Уведомления: ВКЛ (хэш: {MASK})" + C.RESET)
            else:
                print(C.Y + "🔕 Уведомления: ВЫКЛ" + C.RESET)

            print("\nВыберите действие:\n")
            print(C.Y + "1)" + C.W + " Изменить уровни опасности")
            print(C.Y + "2)" + C.W + " Вернуть к стандартным")
            print(C.Y + "3)" + C.W + " Настройки уведомлений")
            print(C.Y + "4)" + C.W + " Назад\n")

            sec_choice = input(C.Y + "Выберите пункт: " + C.RESET)

            if sec_choice in ("1", "2"):
                pending_dangers = dangers.copy()
                if sec_choice == "1":
                    print(C.W + "\nДля каждого уровня укажите 1 (опасный) или 0 (безопасный):\n")
                    for level, enabled in dangers.items():
                        current = int(enabled)
                        while True:
                            value = input(C.W + f"{level} (текущее: {current}): ")
                            if value in ("1", "0"):
                                pending_dangers[level] = value == "1"
                                break
                            print(C.R + "❌ Неверный ввод! Введите 1 или 0." + C.RESET)
                try:
                    if sec_choice == "1":
                        save_settings(pending_dangers)
                        print(C.G + "\n✅ Настройки обновлены." + C.RESET)
                    else:
                        pending_dangers = restoretodefaults()
                        print(C.G + "\n✅ Настройки возвращены к стандартным." + C.RESET)
                    dangers = pending_dangers
                except OSError as exc:
                    print(C.R + f"\n❌ Не удалось сохранить настройки анализа: {exc}" + C.RESET)

                input(C.Y + "\n⏎ Нажмите Enter, чтобы вернуться в меню..." + C.RESET)

            elif sec_choice == '3':
                print("\n" + C.C + "═" * 40 + C.RESET)
                print(C.C + "    НАСТРОЙКИ УВЕДОМЛЕНИЙ" + C.RESET)
                print(C.C + "═" * 40 + C.RESET + "\n")

                available = bool(notification_url())
                _, enabled_preference = load_config(NOTIFICATION_CONFIG)
                if not available:
                    print(C.Y + "🔕 Уведомления отключены. " + NOTIFICATION_URL_REQUIRED + C.RESET)

                if enabled_preference and user_hash:
                    if available:
                        print(C.G + "🔔 Уведомления включены" + C.RESET)
                    print(C.C + f"🔑 Хэш: {MASK}" + C.RESET)
                    print("\nВыберите действие:")
                    if available:
                        print(C.Y + "1)" + C.W + " Изменить user_hash")
                    print(C.Y + "2)" + C.W + " Отключить уведомления")
                    print(C.Y + "3)" + C.W + " Назад")

                    notify_choice = input(C.Y + "\nВыберите пункт: " + C.RESET)

                    if notify_choice == "1" and available:
                        previous_hash = user_hash
                        user_hash, notifications_enabled = setup_notifications(change_hash=True)
                        if user_hash != previous_hash:
                            print(C.G + "\n✅ Хэш обновлен!" + C.RESET)
                        input(C.Y + "\n⏎ Нажмите Enter..." + C.RESET)
                    elif notify_choice == "2":
                        if save_notification_settings(user_hash, False):
                            notifications_enabled = False
                            print(C.Y + "\n🔕 Уведомления отключены" + C.RESET)
                        input(C.Y + "\n⏎ Нажмите Enter..." + C.RESET)
                elif available:
                    print(C.Y + "🔕 Уведомления отключены" + C.RESET)
                    print("\nВыберите действие:")
                    print(C.Y + "1)" + C.W + " Включить уведомления")
                    print(C.Y + "2)" + C.W + " Назад")

                    notify_choice = input(C.Y + "\nВыберите пункт: " + C.RESET)
                    if notify_choice == "1":
                        user_hash, notifications_enabled = setup_notifications()
                else:
                    input(C.Y + "\n⏎ Нажмите Enter..." + C.RESET)

        elif choice == "4":
            print(C.W + "\n👋 До свидания!" + C.RESET)
            break

        else:
            print(C.R + "❌ Неверный ввод!" + C.RESET)
            input(C.Y + "⏎ Нажмите Enter..." + C.RESET)


if __name__ == "__main__":
    main()
