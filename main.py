from menu import menu
from colors import C

from realtimeparser import start_mc_realtime
from log_parser import parse_line, parse_file


def main():
    while True:
        choice = menu()

        # === REALTIME MODE ===
        if choice == "1":
            path = input(C.Y + "Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n--- Чтение лога в реальном времени ---\n" + C.RESET)

            try:
                i = 1
                for parsed in start_mc_realtime(path):

                    level = parsed["level"].strip().upper()

                    # выбираем цвет
                    color = C.R if level in ("WARN", "ERROR", "CRITICAL") else C.Y
                    print(color + f"{i})")

                    print(color + "──────────── LOG ENTRY ────────────")

                    print(f"RAW:   {parsed['raw']}")
                    print(f"FORMAT:   {parsed['format']}")
                    print(f"LEVEL:   {parsed['level']}")

                    if parsed["date"] != "N":
                        print(f"TIME:   {parsed['time']}")
                        print(f"DATE:   {parsed['date']}")
                    else:
                        print(f"TIME:   {parsed['time']}")

                    print(f"MESSAGE:   {parsed['message']}")
                    print(f"SOURCE:   {parsed['source']}\n")
                    i+=1
            except Exception as e:
                print(C.R + "\nОшибка: " + str(e) + C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")


        # === ONETIME ANALYZE ===
        elif choice == "2":
            path = input(C.Y + "Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n--- Чтение и анализ лога ---\n" + C.RESET)
            errors = []

            try:
                parsedlogs = list(parse_file(path))
            except Exception as e:
                print(C.R + "\nОшибка: " + str(e) + C.RESET)
                continue

            for i in range(len(parsedlogs)):
                level = parsedlogs[i]["level"].strip().upper()

                color = C.R if level in ("WARN", "ERROR") else C.Y
                print(color + f"{i+1})")

                print("──────────── LOG ENTRY ────────────")
                print(f"RAW:    {parsedlogs[i]['raw']}")
                print(f"FORMAT: {parsedlogs[i]['format']}")
                print(f"LEVEL:  {parsedlogs[i]['level']}")

                if parsedlogs[i]["date"] != "N":
                    print(f"TIME:   {parsedlogs[i]['date']} {parsedlogs[i]['time']}")
                else:
                    print(f"TIME:   {parsedlogs[i]['time']}")

                print(f"MESSAGE: {parsedlogs[i]['message']}")
                print(f"SOURCE:  {parsedlogs[i]['source']}\n")

                if level in ("WARN", "ERROR"):
                    errors.append(i)

            if errors:
                normerrors = [i+1 for i in errors]
                print(C.R + "Ошибки или предупреждения в строках:", *normerrors, C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")


        elif choice == "3":
            break

        else:
            input(C.R + "Неверный ввод! Enter..." + C.RESET)


if __name__ == "__main__":
    main()
