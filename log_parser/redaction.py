"""Mask secrets and personal data before log text is parsed or displayed."""

import ipaddress
import json
import re
from urllib.parse import unquote


MASK = "******"

_SENSITIVE_KEYS = frozenset("""
    password passwd pwd passphrase secret secrets clientsecret signingsecret
    webhooksecret sharedsecret credentials credential passwordhash passwordvalue
    token accesstoken refreshtoken idtoken auth authcode authorizationcode oauthcode
    authtoken oauthtoken apitoken securitytoken sessiontoken sessionid sessionkey jwt jwtsecret
    apikey xapikey apiaccesskey accesskey accesskeyid awsaccesskeyid accountkey
    secretkey secretaccesskey awssecretaccesskey awssessiontoken privatekey
    sshprivatekey encryptionkey signingkey recoverycode otp pin
    authorization proxyauthorization cookie cookies setcookie csrf csrftoken xcsrftoken
    xauthtoken xaccesstoken userhash connectionstring databaseurl
    xamzcredential xamzsecuritytoken xamzsignature xgoogcredential xgoogsignature
    user userid username email emailaddress useremail phone phonenumber mobilephone
    firstname lastname fullname displayname realname streetaddress postaladdress address
    ssn socialsecuritynumber creditcard creditcardnumber cardnumber cvv cvc iban
    ip ipaddress clientip remoteip remoteaddr sourceip destinationip
    xforwardedfor xrealip forwardedfor macaddress
""".split())
_KEY_PREFIXES = {"db", "database", "smtp", "redis", "github", "gitlab", "slack", "discord",
                 "openai", "stripe", "admin", "user", "service", "x"}
_HEADERS = {"authorization", "proxyauthorization", "cookie", "cookies", "setcookie", "xforwardedfor"}
_QUERY_SECRETS = {"code", "key", "sig", "signature", "session", "samlrequest", "samlresponse"}

_FIELD = re.compile(
    r"""(?<![\w.%-])(?P<key>"(?:\\.|[^"\\])*?"|'[^'\\]*?'|"""
    r"""(?:api[ -]key|access[ -]token|refresh[ -]token|private[ -]key|client[ -]secret|"""
    r"""credit[ -]card(?:[ -]number)?|phone[ -]number|email[ -]address)|[a-z%][\w.%-]*)"""
    r"""(?:[ \t]*(?:=|:(?!//))[ \t]*|[ \t]+is[ \t]+)""",
    re.IGNORECASE,
)
_VALUE_TOKEN = re.compile(r"\S+")
_STRUCTURED_TOKEN = re.compile(r"""[^\s,}\]]+""")
_QUERY_TOKEN = re.compile(r"""[^&\s#"'<>]+""")
_QUOTED = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''', re.VERBOSE)
_BRACKETS = re.compile(r'''["'{}\[\]]''')
_AUTH = re.compile(r"\b(?:Bearer|Basic)[ \t]+[a-zA-Z0-9._~+/%=-]+", re.IGNORECASE)
_PEM_BEGIN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?:-----)?")
_PEM_END = re.compile(r"-----END [A-Z0-9 ]*PRIVATE KEY-----")
_URI_USERINFO = re.compile(r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^/\s?#@\"'<>]+@", re.IGNORECASE)
_WEBHOOK = re.compile(
    r"\bhttps?://(?:(?:[a-z]+\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/"
    r"|hooks\.slack\.com/services/)[^\s\"'<>?#]+",
    re.IGNORECASE,
)
_ACCESS_USERS = re.compile(
    r"^(?P<host>\s*\S+[ \t]+)(?P<ident>\S+)(?P<gap>[ \t]+)(?P<user>\S+)"
    r"(?=[ \t]+\[[^\]\r\n]+\][ \t]+\"\S+[ \t]+[^\r\n]*\bHTTP/[\d.]+\")"
)
_SSH_USER = re.compile(r"\b(?:for (?:invalid )?user|invalid user)[ \t]+\S+(?=[ \t]+from\b)", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.!#$%&'*+^{}|~-]+@(?:[\w-]+\.)+[\w-]{2,63}")
_IPV4 = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?!\d|\.\d)")
_IPV6 = re.compile(
    r"(?<![\w:])(?=[0-9a-f]*:[0-9a-f]*:)[0-9a-f:]+(?:\.[0-9]{1,3}){0,3}"
    r"(?:%[\w.-]+)?(?![\w:])", re.IGNORECASE,
)
_MAC = re.compile(r"(?<![\w:])(?:[a-f0-9]{2}[:-]){5}[a-f0-9]{2}(?![\w:])", re.IGNORECASE)
_PHONE = re.compile(
    r"(?<![\w+\d])(?:\+[1-9]\d{6,14}|\+\d{1,3}[ -]\d{2,4}[ -]\d{2,4}[ -]\d{2,4}(?:[ -]\d{2,4})?"
    r"|(?:\(\d{3}\)[ -]?|\d{3}-)\d{3}-\d{4})(?![\w\d])"
)
_SSN = re.compile(r"(?<![\w-])\d{3}-\d{2}-\d{4}(?![\w-])")
_CARD = re.compile(r"(?<![\w+.-])\d(?:[ -]?\d){12,18}(?![\w.-])")
_TOKEN = re.compile(
    r"(?<![\w-])(?:eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    r"|(?:AKIA|ASIA)[A-Z0-9]{16}"
    r"|(?:gh[pousr]_|github_pat_|glpat-|xox[baprs]-|sk_(?:live|test)_|sk-(?:proj-|svcacct-)?"
    r"|AIza|npm_|pypi-AgEIcHlwaS5vcmc)[A-Za-z0-9_-]{16,})(?![\w-])"
)


def _key_name(key):
    return re.sub(r"[^a-z0-9]", "", unquote(key).lower())


def _sensitive_key(key):
    name = _key_name(key)
    if name in _SENSITIVE_KEYS:
        return True
    prefix, *suffix = re.split(r"[_.-]", unquote(key.lower()), maxsplit=1)
    return bool(suffix) and prefix in _KEY_PREFIXES and _key_name(suffix[0]) in _SENSITIVE_KEYS


def _mask_ip(match):
    address = match[0]
    if ":" not in address:
        return MASK if all(int(octet) <= 255 for octet in address.split(".")) else address
    try:
        ipaddress.IPv6Address(address)
    except ValueError:
        return address
    return MASK


def _mask_card(match):
    digits = [int(char) for char in reversed(match[0]) if char.isdecimal()]
    doubled = [2 * digit for digit in digits[1::2]]
    checksum = sum(digits[::2]) + sum(digit - 9 if digit > 9 else digit for digit in doubled)
    return MASK if checksum % 10 == 0 else match[0]


def _mask_access_users(match):
    ident = "-" if match["ident"] == "-" else MASK
    user = "-" if match["user"] == "-" else MASK
    return match["host"] + ident + match["gap"] + user


def _mask_email(match):
    # Preserve the host of a URL whose user info was masked.
    return match[0] if match[0].startswith(MASK + "@") else MASK


def _container_end(text, start, depth):
    while match := _BRACKETS.search(text, start):
        char = match[0]
        start = match.end()
        if char in "\"'":
            quoted = _QUOTED.match(text, match.start())
            if not quoted:
                return len(text), depth
            start = quoted.end()
        elif char in "[{":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start, 0
    return len(text), depth


def _mask_json(text, depth):
    changed = False

    def mask_value(value):
        nonlocal changed
        if isinstance(value, list):
            return [mask_value(item) for item in value]
        if isinstance(value, str):
            safe = _mask_text(value, depth + 1)
            changed |= safe != value
            return safe
        if isinstance(value, int) and not isinstance(value, bool):
            number = str(value)
            if (card := _CARD.fullmatch(number)) and _mask_card(card) == MASK:
                changed = True
                return MASK
        return value

    def mask_object(pairs):
        nonlocal changed
        result = {}
        for key, value in pairs:
            if _sensitive_key(key):
                changed |= value != MASK
                safe_value = MASK
            else:
                safe_value = mask_value(value)
            safe_key = _mask_text(key, depth + 1)
            changed |= safe_key != key
            result[safe_key] = safe_value
        return result

    try:
        decoder = json.JSONDecoder(object_pairs_hook=mask_object)
        start = len(text) - len(text.lstrip())
        value, end = decoder.raw_decode(text, start)
        if not text[end:].strip():
            value = mask_value(value)
            if changed:
                return text[:start] + json.dumps(value, ensure_ascii=True) + text[end:]
            return text
    except json.JSONDecodeError:
        pass
    return None


class LogRedactor:
    """Keep continuation state for one file or monitoring session."""

    def __init__(self):
        self.private_key = False
        self.pending_value = False
        self.container_depth = 0
        self.open_quote = ""
        self.folded_header = False

    def redact(self, text, depth=0):
        if depth > 12:
            return MASK
        if self.private_key:
            self.private_key = not _PEM_END.search(text)
            return MASK
        if self.open_quote:
            if quoted := _QUOTED.match(self.open_quote + text):
                self.open_quote = ""
                return MASK + self.redact(text[quoted.end() - 1:], depth + 1)
            return MASK
        if self.container_depth:
            end, self.container_depth = _container_end(text, 0, self.container_depth)
            return MASK + self.redact(text[end:], depth + 1) if end < len(text) else MASK
        if self.pending_value:
            if text.strip():
                self.pending_value = False
                if text.lstrip().startswith(("{", "[")):
                    _, self.container_depth = _container_end(text, 0, 0)
                return MASK
            return text
        if self.folded_header:
            if text.startswith((" ", "\t")) and text.strip():
                return MASK
            self.folded_header = False
        if text.lstrip().startswith(("{", "[")):
            try:
                safe = _mask_json(text, depth)
            except (RecursionError, ValueError):
                return MASK
            if safe is not None:
                return safe
        if begin := _PEM_BEGIN.search(text):
            end = _PEM_END.search(text, begin.end())
            if not end:
                self.private_key = True
                return self.redact_prefix(text[:begin.start()] + MASK)
            return self.redact(text[:begin.start()] + MASK + text[end.end():], depth + 1)
        return self.redact_prefix(text)

    def redact_prefix(self, text):
        text = _ACCESS_USERS.sub(_mask_access_users, text, count=1)
        text = _SSH_USER.sub(lambda match: match[0].rsplit(None, 1)[0] + " " + MASK, text)
        text = _URI_USERINFO.sub(lambda match: match["scheme"] + MASK + "@", text)
        text = _WEBHOOK.sub(MASK, text)
        # Advance over each masked value so assignment-like content inside it stays hidden.
        parts = []
        start = 0
        for field in _FIELD.finditer(text):
            if field.start() < start:
                continue
            key = field["key"]
            quote = key[0] if key[0] in "\"'" else ""
            if key.startswith('"'):
                try:
                    key = json.loads(key)
                except json.JSONDecodeError:
                    key = key[1:-1]
            elif key.startswith("'"):
                key = key[1:-1]
            query = field.start() > 0 and text[field.start() - 1] in "?&#"
            if not _sensitive_key(key) and not (query and _key_name(key) in _QUERY_SECRETS):
                continue

            value = field.end()
            header = not query and _key_name(key) in _HEADERS
            parts.append(text[start:value])
            if value == len(text):
                self.pending_value = not query
                self.folded_header = header
                start = value
            elif text[value] in "\"'":
                quoted = _QUOTED.match(text, value)
                parts.append(text[value] + MASK + text[value] if quoted else MASK)
                start = quoted.end() if quoted else len(text)
                if not quoted:
                    self.open_quote = text[value]
                continue
            elif not query and text[value] in "[{":
                start, self.container_depth = _container_end(text, value, 0)
            elif header:
                # Headers may carry several values, including space-delimited credentials.
                start = len(text)
                self.folded_header = True
            else:
                if query:
                    token = _QUERY_TOKEN.match(text, value)
                elif quote:
                    token = _STRUCTURED_TOKEN.match(text, value)
                else:
                    token = _PHONE.match(text, value) or _CARD.match(text, value) or _VALUE_TOKEN.match(text, value)
                start = token.end() if token else value
            parts.append(quote + MASK + quote)
        parts.append(text[start:])
        text = "".join(parts)
        for pattern in (_AUTH, _TOKEN, _MAC):
            text = pattern.sub(MASK, text)
        text = _EMAIL.sub(_mask_email, text)
        for pattern in (_IPV6, _IPV4):
            text = pattern.sub(_mask_ip, text)
        text = _PHONE.sub(MASK, text)
        text = _SSN.sub(MASK, text)
        return _CARD.sub(_mask_card, text)


def _mask_text(text, depth):
    if depth > 12:
        return MASK
    if text.lstrip().startswith(("{", "[")) and "\n" in text.rstrip("\r\n"):
        try:
            safe = _mask_json(text, depth)
        except (RecursionError, ValueError):
            return MASK
        if safe is not None:
            return safe
    redactor = LogRedactor()
    lines = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        lines.append(redactor.redact(content, depth) + line[len(content):])
    return "".join(lines)


def mask_sensitive(text):
    """Mask standalone text, including multiline messages sent as notifications."""
    return _mask_text(text, 0)
