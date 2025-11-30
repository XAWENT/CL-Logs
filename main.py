from menu import menu
from colors import C
import os
from realtimeparser import start_mc_realtime
from log_parser import parse_line, parse_file

dangers = {'WARN': True, 'ERROR': True, 'INFO': False}
def main():
    while True:
        choice = menu()
        truedangers = [leveld for leveld in dangers if dangers[leveld]]

        if choice == "1":
            path = input(C.Y + "Введите путь к вашему логу: " + C.RESET)
            print(C.C + "\n--- Чтение лога в реальном времени ---\n" + C.RESET)

            try:
                i = 1
                for parsed in start_mc_realtime(path):

                    level = parsed["level"].strip().upper()

                    if dangers[level] == True:
                        color = C.R
                    else:
                        color = C.Y

                    print(color + f"{i})")

                    print("──────────── LOG ENTRY ────────────")

                    print(f"RAW:   {parsed['raw']}")
                    print(f"FORMAT:   {parsed['format']}")
                    print(f"LEVEL:   {parsed['level']}")

                    if parsed["date"] != "N":
                        print(f"TIME:   {parsed['time']}")
                        print(f"DATE:   {parsed['date']}")
                    else:
                        print(f"TIME:   {parsed['time']}")

                    print(f"MESSAGE:   {parsed['message']}")
                    print(f"SOURCE:   {parsed['source']}\n"+C.RESET)
                    i+=1
            except Exception as e:
                print(C.R + "\nОшибка: " + str(e) + C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")
            os.system('cls' if os.name == 'nt' else 'clear')



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

                if dangers[level] == True:
                    color = C.R
                else:
                    color = C.Y
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
                print(f"SOURCE:  {parsedlogs[i]['source']}\n"+C.RESET)

                if dangers[level] == True:
                    errors.append(i)

            if errors:
                normerrors = [i+1 for i in errors]
                print(C.R + "Нежелательные события в строках:", *normerrors, C.RESET)

            input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")
            os.system('cls' if os.name == 'nt' else 'clear')



        elif choice == "3":
            print(C.W + f"Сейчас система считает нежелательными: {', '.join(map(str, truedangers))}")
            print('Хотите изменить?\n')
            print(C.Y + "1)" + C.W + 'ДА.')
            print(C.Y + "2)" + C.W + 'НЕТ.\n')
            sec_choice = input(C.Y + "Выберите пункт: " + C.RESET)

            if sec_choice == '2':
                continue
            elif sec_choice == '1':
                print(C.W + 'Для кадой угрозы укажите 1 или 0\n')
                for leveld in dangers:
                    while True:
                        oneorzero = input(C.W + f'Уровень для {leveld}: ')
                        if oneorzero == '1':
                            dangers[leveld] = True
                            break
                        elif oneorzero == '0':
                            dangers[leveld] = False
                            break
                        else:
                            print(C.R + 'Неверный ввод! Введите 1 или 0!' + C.RESET)
                print('\n')
                truedangers = [leveld for leveld in dangers if dangers[leveld]]
                if truedangers:
                    print(f"Теперь нежелательными счиаются: {', '.join(map(str, truedangers))}")
                else:
                    print('Сейчас в системе отсутствуют данные о нежелательных событиях.')
                input(C.Y + "\nНажмите Enter, чтобы вернуться в меню...")
                os.system('cls' if os.name == 'nt' else 'clear')

        elif choice == "4":
            break

        else:
            input(C.R + "Неверный ввод! Enter..." + C.RESET)
            os.system('cls' if os.name == 'nt' else 'clear')


if __name__ == "__main__":
    main()
#C:\Users\timof\AppData\Roaming\.minecraft\logs\latest.log