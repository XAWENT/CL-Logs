import re

class KeyValueParser:
    def match(self, line):
        line = line.strip()

        # 1. если лог начинается с месяца → это syslog, не kv
        if re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:", line):
            return False

        # 2. если есть timestamp → это не kv
        if re.search(r"\d{4}-\d{2}-\d{2}", line):
            return False
        if re.search(r"\d{2}:\d{2}:\d{2}", line):
            return False

        # 3. если начинается не с key=
        if not re.match(r"^[A-Za-z0-9_\-\.]+=.+", line):
            return False

        # 4. иначе — чистый KV формат
        return True


    def parse(self, line):
        kv={}
        for token in line.split():
            if "=" in token:
                k,v=token.split("=",1)
                kv[k]=v

        return {
            "format":"kv",
            "raw": line,
            "date":"N",
            "time":"N",
            "level":"N",
            "kv": kv,
            "message": line
        }
