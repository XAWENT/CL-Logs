from menu import menu
from colors import C
import os

from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime
from logic.settings import load_settings, save_settings, restoretodefaults


def main():
    dangers = load_settings()
    while True:

        os.system("cls" if os.name == "nt" else "clear")

        choice = menu()
        truedangers = [lvl for lvl in dangers if dangers[lvl]]

        if choice == "1":
            path = input(C.Y + "Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n--- Чтение лога в реальном времени ---\n" + C.RESET)

            try:
                for entry in iterate_realtime(path, dangers):
                    color = C.R if entry["is_danger"] else C.Y

                    print(color + f"{entry['index']})")
                    print("──────────── LOG ENTRY ────────────")

                    print(f"RAW:    {entry['raw']}")
                    print(f"FORMAT: {entry['format']}")
                    print(f"LEVEL:  {entry['level']}")

                    if entry["date"] != "N":
                        print(f"DATE:   {entry['date']}")
                        print(f"TIME:   {entry['time']}")
                    else:
                        print(f"TIME:   {entry['time']}")

                    print(f"MESSAGE:{entry['message']}")
                    print(f"SOURCE: {entry['source']}\n" + C.RESET)

            except Exception as e:
                print(C.R + "\nОшибка: " + str(e) + C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню..." + C.RESET)


        elif choice == "2":
            path = input(C.Y + "Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n--- Чтение и анализ лога ---\n" + C.RESET)

            try:
                entries, danger_lines = analyze_log(path, dangers)
            except Exception as e:
                print(C.R + "\nОшибка: " + str(e) + C.RESET)
                continue

            for entry in entries:
                color = C.R if entry["is_danger"] else C.Y

                print(color + f"{entry['index']})")
                print("──────────── LOG ENTRY ────────────")
                print(f"RAW:    {entry['raw']}")
                print(f"FORMAT: {entry['format']}")
                print(f"LEVEL:  {entry['level']}")

                if entry["date"] != "N":
                    print(f"TIME:   {entry['date']} {entry['time']}")
                else:
                    print(f"TIME:   {entry['time']}")

                print(f"MESSAGE:{entry['message']}")
                print(f"SOURCE: {entry['source']}\n" + C.RESET)

            if danger_lines:
                print(C.R + "Нежелательные события в строках:", *danger_lines, C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")
            os.system("cls" if os.name == "nt" else "clear")


        elif choice == "3":
            print(C.W + f"Сейчас система считает нежелательными: {', '.join(truedangers)}")
            print("Хотите изменить?\n")
            print(C.Y + "1)" + C.W + " ДА.")
            print(C.Y + "2)" + C.W + " НЕТ.")
            print(C.Y + "3)" + C.W + " Вернуть к стандартным.\n")

            sec_choice = input(C.Y + "Выберите пункт: " + C.RESET)

            if sec_choice == "2":
                continue
            elif sec_choice == "1":
                print(C.W + "Для каждого уровня укажите 1 или 0.\n")

                for lvl in dangers:
                    while True:
                        val = input(C.W + f"{lvl}: ")
                        if val == "1":
                            dangers[lvl] = True
                            break
                        elif val == "0":
                            dangers[lvl] = False
                            break
                        else:
                            print(C.R + "Неверный ввод! 1 или 0." + C.RESET)

                save_settings(dangers)
                input(C.Y + "\nНастройки обновлены. Enter..." + C.RESET)
            elif sec_choice == '3':
                dangers = restoretodefaults()
                input(C.Y + "\nНастройки возвращены к стандартным. Enter..." + C.RESET)
        elif choice == "4":
            break

        else:
            input(C.R + "Неверный ввод! Enter..." + C.RESET)
            os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    main()
