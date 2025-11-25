from log_parser import parse_line, parse_file, get_errors
logs = parse_file('linux_logs.txt')
for i in range(45, 104):
    print(logs[i])
    print('  ')
