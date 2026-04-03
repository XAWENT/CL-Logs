from menu import menu
from colors import C
import os
import json
import requests

from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime
from logic.settings import load_settings, save_settings, restoretodefaults

BASE_URL = "http://94.183.235.102:5000"


def check_notifications_status():
    user_hash = None
    notifications_enabled = False

    try:
        if os.path.exists("user_config.json"):
            with open("user_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                user_hash = data.get("user_hash")
                if user_hash:
                    notifications_enabled = True
    except:
        pass

    return user_hash, notifications_enabled


def setup_notifications():
    print(C.C + "\n" + "═" * 50 + C.RESET)
    print(C.C + "         НАСТРОЙКА СИСТЕМЫ УВЕДОМЛЕНИЙ" + C.RESET)
    print(C.C + "═" * 50 + C.RESET + "\n")

    saved_hash = None
    try:
        if os.path.exists("user_config.json"):
            with open("user_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_hash = data.get("user_hash")
                if saved_hash:
                    print(C.Y + f"📋 Найден сохраненный user_hash: {saved_hash}" + C.RESET)
                    use_saved = input(C.Y + "Использовать его? (y/n): " + C.RESET).lower()
                    if use_saved == 'y':
                        return saved_hash, True
    except:
        pass

    while True:
        print(C.W + "📝 Для отправки уведомлений нужен ваш user_hash." + C.RESET)
        print(C.W + "   Его можно получить у администратора системы.\n" + C.RESET)

        user_hash = input(C.Y + "Введите ваш user_hash (или Enter для пропуска): " + C.RESET).strip().upper()

        if not user_hash:
            print(C.Y + "🔕 Уведомления отключены." + C.RESET)
            return None, False

        if len(user_hash) < 8:
            print(C.R + "❌ Хэш слишком короткий. Минимум 8 символов." + C.RESET)
            continue

        print(C.C + "\n🔍 Проверяем соединение с сервером..." + C.RESET)
        try:
            health_response = requests.get(f"{BASE_URL}/", timeout=3)
            if health_response.status_code != 200:
                print(C.R + "❌ Сервер недоступен. Проверьте запущен ли сервер на порту 5000." + C.RESET)
                retry = input(C.Y + "🔄 Попробовать снова? (y/n): " + C.RESET).lower()
                if retry != 'y':
                    return None, False
                continue

            test_data = {
                "user_hash": user_hash,
                "message": "🔧 Тестовая проверка системы уведомлений\n✅ Соединение установлено",
                "level": "INFO"
            }

            response = requests.post(
                f"{BASE_URL}/send",
                headers={"Content-Type": "application/json"},
                json=test_data,
                timeout=5
            )

            if response.status_code == 200:
                try:
                    with open("user_config.json", "w", encoding="utf-8") as f:
                        json.dump({"user_hash": user_hash}, f)
                except:
                    pass

                user_data = response.json().get('user', {})
                print(C.G + f"\n✅ Настройка завершена успешно!" + C.RESET)
                print(C.C + f"👤 Пользователь: {user_data.get('first_name', 'Unknown')}" + C.RESET)
                return user_hash, True

            elif response.status_code == 404:
                error_msg = response.json().get('error', 'User not found')
                print(C.R + f"❌ Ошибка: {error_msg}" + C.RESET)
                print(C.Y + "🔍 Проверьте правильность user_hash." + C.RESET)
            else:
                print(C.R + f"❌ Ошибка сервера: {response.status_code}" + C.RESET)

        except requests.exceptions.ConnectionError:
            print(C.R + "❌ Не удалось подключиться к серверу." + C.RESET)
            retry = input(C.Y + "🔄 Попробовать снова? (y/n): " + C.RESET).lower()
            if retry != 'y':
                return None, False
            continue
        except requests.exceptions.Timeout:
            print(C.R + "⏰ Таймаут при подключении к серверу." + C.RESET)
            retry = input(C.Y + "🔄 Попробовать снова? (y/n): " + C.RESET).lower()
            if retry != 'y':
                return None, False
            continue
        except Exception as e:
            print(C.R + f"❌ Ошибка: {str(e)}" + C.RESET)
            retry = input(C.Y + "🔄 Попробовать снова? (y/n): " + C.RESET).lower()
            if retry != 'y':
                return None, False
            continue


def send_notification(level, message, source, timestamp="", user_hash=None):
    if not user_hash:
        return False

    try:
        if level in ["ERROR", "WARN"]:
            telegram_message = f"""
⚠️ {level}
📝 Сообщение: {message}
"""

            send_data = {
                "user_hash": user_hash,
                "message": telegram_message.strip(),
                "level": level
            }

            response = requests.post(
                f"{BASE_URL}/send",
                headers={"Content-Type": "application/json"},
                json=send_data,
                timeout=10
            )

            if response.status_code == 200:
                return True
            else:
                return False

        if level == "ERROR":
            email_subject = f"🚨 КРИТИЧЕСКАЯ ОШИБКА в системе - {timestamp}"
            email_message = f"""
🚨 КРИТИЧЕСКАЯ ОШИБКА В СИСТЕМЕ

⏰ Время события: {timestamp}
📁 Источник: {source}
🔴 Уровень: {level}

📋 Сообщение ошибки:
{message}

⚠️ Требуется немедленное вмешательство!
"""

            email_data = {
                "user_hash": user_hash,
                "subject": email_subject,
                "message": email_message.strip()
            }

            response = requests.post(
                f"{BASE_URL}/send_email",
                headers={"Content-Type": "application/json"},
                json=email_data,
                timeout=10
            )

            return response.status_code == 200

    except:
        return False


def main():
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

            if not notifications_enabled:
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

                    if notifications_enabled and user_hash and entry["level"] in ["ERROR", "WARN"] and entry[
                        "is_danger"]:
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
                print(C.R + "\n❌ Ошибка: " + str(e) + C.RESET)

            input(C.Y + "\n⏎ Нажмите Enter, чтобы вернуться в меню..." + C.RESET)


        elif choice == "2":
            path = input(C.Y + "📁 Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n" + "═" * 50 + C.RESET)
            print(C.C + "          АНАЛИЗ ЛОГ-ФАЙЛА" + C.RESET)
            print(C.C + "═" * 50 + C.RESET + "\n")

            if not notifications_enabled:
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
                print(C.R + "❌ Ошибка: " + str(e) + C.RESET)
                input(C.Y + "\n⏎ Нажмите Enter, чтобы продолжить..." + C.RESET)
                continue

            error_count = 0
            warn_count = 0
            sent_count = 0

            for entry in entries:
                if entry["level"] == "ERROR":
                    icon = "❌"
                    color = C.R
                    error_count += 1 if entry["is_danger"] else 0
                elif entry["level"] == "WARN":
                    icon = "⚠️"
                    color = C.Y
                    warn_count += 1 if entry["is_danger"] else 0
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

                if notifications_enabled and user_hash and entry["level"] in ["ERROR", "WARN"] and entry["is_danger"]:
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

            if notifications_enabled and user_hash:
                print(C.G + f"🔔 Уведомления: ВКЛ (хэш: {user_hash[:8]}...)" + C.RESET)
            else:
                print(C.Y + "🔕 Уведомления: ВЫКЛ" + C.RESET)

            print("\nВыберите действие:\n")
            print(C.Y + "1)" + C.W + " Изменить уровни опасности")
            print(C.Y + "2)" + C.W + " Вернуть к стандартным")
            print(C.Y + "3)" + C.W + " Настройки уведомлений")
            print(C.Y + "4)" + C.W + " Назад\n")

            sec_choice = input(C.Y + "Выберите пункт: " + C.RESET)

            if sec_choice == "1":
                print(C.W + "\nДля каждого уровня укажите 1 (опасный) или 0 (безопасный):\n")
                for lvl in dangers:
                    current = "1" if dangers[lvl] else "0"
                    while True:
                        val = input(C.W + f"{lvl} (текущее: {current}): ")
                        if val == "1":
                            dangers[lvl] = True
                            break
                        elif val == "0":
                            dangers[lvl] = False
                            break
                        else:
                            print(C.R + "❌ Неверный ввод! Введите 1 или 0." + C.RESET)
                save_settings(dangers)
                input(C.Y + "\n✅ Настройки обновлены. Enter..." + C.RESET)

            elif sec_choice == '2':
                dangers = restoretodefaults()
                save_settings(dangers)
                input(C.Y + "\n✅ Настройки возвращены к стандартным. Enter..." + C.RESET)

            elif sec_choice == '3':
                print("\n" + C.C + "═" * 40 + C.RESET)
                print(C.C + "    НАСТРОЙКИ УВЕДОМЛЕНИЙ" + C.RESET)
                print(C.C + "═" * 40 + C.RESET + "\n")

                if notifications_enabled and user_hash:
                    print(C.G + f"🔔 Уведомления включены" + C.RESET)
                    print(C.C + f"🔑 Хэш: {user_hash}" + C.RESET)
                    print("\nВыберите действие:")
                    print(C.Y + "1)" + C.W + " Изменить user_hash")
                    print(C.Y + "2)" + C.W + " Отключить уведомления")
                    print(C.Y + "3)" + C.W + " Назад")

                    notify_choice = input(C.Y + "\nВыберите пункт: " + C.RESET)

                    if notify_choice == "1":
                        new_hash, enabled = setup_notifications()
                        if enabled:
                            user_hash = new_hash
                            notifications_enabled = True
                            print(C.G + "\n✅ Хэш обновлен!" + C.RESET)
                        else:
                            notifications_enabled = False
                            print(C.Y + "\n🔕 Уведомления отключены" + C.RESET)
                        input(C.Y + "\n⏎ Нажмите Enter..." + C.RESET)
                    elif notify_choice == "2":
                        notifications_enabled = False
                        try:
                            if os.path.exists("user_config.json"):
                                os.remove("user_config.json")
                        except:
                            pass
                        print(C.Y + "\n🔕 Уведомления отключены" + C.RESET)
                        input(C.Y + "\n⏎ Нажмите Enter..." + C.RESET)
                else:
                    print(C.Y + "🔕 Уведомления отключены" + C.RESET)
                    print("\nВыберите действие:")
                    print(C.Y + "1)" + C.W + " Включить уведомления")
                    print(C.Y + "2)" + C.W + " Назад")

                    notify_choice = input(C.Y + "\nВыберите пункт: " + C.RESET)
                    if notify_choice == "1":
                        user_hash, notifications_enabled = setup_notifications()

        elif choice == "4":
            print(C.W + "\n👋 До свидания!" + C.RESET)
            break

        else:
            print(C.R + "❌ Неверный ввод!" + C.RESET)
            input(C.Y + "⏎ Нажмите Enter..." + C.RESET)


if __name__ == "__main__":
    main()
