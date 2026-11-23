"""Keyboard-driven console for CL-Logs."""
from collections import Counter
from pathlib import Path
from random import choice
import re
from threading import Event
from time import monotonic

import requests
from rich.cells import get_character_cell_size
from rich.segment import Segment
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.filter import LineFilter
from textual.screen import ModalScreen, Screen
from textual.theme import Theme
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, SelectionList, Static
from textual.worker import get_current_worker

from log_parser.redaction import mask_sensitive
from logic.notifications import (
    NOTIFICATION_CONFIG, NOTIFICATION_URL_REQUIRED, load_config, notification_url, save_config,
)
from logic.onetime_logic import iter_log_entries
from logic.realtime_logic import iterate_realtime
from logic.settings import default_dangers, load_settings, save_settings


AMBER = Theme("amber", primary="#f0a481", secondary="#cfbaff", foreground="#f2e8dc",
              background="#211c1a", surface="#2e2724", panel="#43362e",
              error="#ffa3a2", warning="#efd080")
SAMPLES = Path(__file__).resolve().parent / "Test logs"


class RevealFrame(LineFilter):
    """Transform painted text only. Every frame keeps the original cell geometry."""

    DURATION = 0.56
    WORD = re.compile(r"[^\W_]+")
    SYMBOLS = "$#@*%+"

    def __init__(self, progress):
        super().__init__()
        self.progress = progress

    def reveal_word(self, match):
        word = match.group()
        # Short stagger keeps adjacent words from settling on the same frame.
        delay = (ord(word[0]) % 5) * 0.025
        fraction = max(0.0, (self.progress - delay) / (1 - delay))
        settled = int(len(word) * fraction)
        return word[:settled] + "".join(
            choice(self.SYMBOLS) if get_character_cell_size(char) == 1 else char
            for char in word[settled:]
        )

    def apply(self, segments, background):
        return [
            segment if segment.control else
            Segment(self.WORD.sub(self.reveal_word, segment.text), segment.style)
            for segment in segments
        ]


def bar(section):
    with Horizontal(classes="bar"):
        yield Label("▌ CL-Logs", classes="brand")
        yield Label(section, classes="section")
        yield Label("Янтарь", classes="theme-name")


class Page(Screen):
    BINDINGS = [Binding("escape", "back", "Назад")]

    def on_mount(self):
        self.app.reveal(self)

    def action_back(self):
        self.app.pop_screen()


class Home(Page):
    AUTO_FOCUS = "#commands"
    BINDINGS = [
        Binding("a", "pick(False)", "Анализ", show=False),
        Binding("m", "pick(True)", "Мониторинг", show=False),
        Binding("s", "settings", "Настройки", show=False),
        Binding("q", "app.quit", "Выход"), Binding("escape", "app.quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield from bar("Консоль")
        with VerticalScroll(classes="page"):
            yield Label("Главное меню", classes="title")
            yield OptionList(
                "A · Открыть файл\nПросмотр и фильтрация записей",
                None,
                "M · Мониторинг\nНовые строки в реальном времени",
                None,
                "S · Настройки\nУровни опасности и уведомления",
                id="commands",
            )
            yield Label("↑ ↓  выбрать     Enter  открыть", classes="hint")
        yield Footer()

    def on_option_list_option_selected(self, event):
        if event.option_index == 2:
            self.action_settings()
        else:
            self.action_pick(event.option_index == 1)

    def action_pick(self, live):
        self.app.push_screen(FilePicker(live))

    def action_settings(self):
        self.app.push_screen(Settings())


class FilePicker(Page):
    AUTO_FOCUS = "#path"
    def __init__(self, live):
        super().__init__()
        self.live = live
        self.samples = sorted(SAMPLES.glob("*.log"))

    def compose(self):
        yield from bar("Мониторинг" if self.live else "Анализ файла")
        with VerticalScroll(classes="page"):
            yield Label("Следить за файлом" if self.live else "Открыть файл", classes="title")
            yield Label("Путь к журналу", classes="caption")
            yield Input(placeholder="~/logs/application.log", id="path")
            with Horizontal(classes="buttons"):
                yield Button("Начать мониторинг" if self.live else "Открыть", id="open-file", variant="primary")
            yield Static("", id="error", markup=False)
            if self.samples:
                yield Label("Примеры из проекта", classes="caption")
                yield OptionList(*(p.name for p in self.samples), id="samples")
        yield Footer()

    @on(Input.Submitted)
    @on(Button.Pressed, "#open-file")
    def open_path(self):
        value = self.query_one(Input).value.strip()
        self.open(Path(value).expanduser())

    def on_option_list_option_selected(self, event):
        self.open(self.samples[event.option_index])

    def open(self, path):
        if not path.is_file():
            self.query_one("#error", Static).update("Файл не найден. Проверьте путь.")
            self.query_one(Input).focus()
            return
        self.app.switch_screen(Journal(path, self.live))


class Details(ModalScreen):
    BINDINGS = [Binding("escape,enter", "dismiss", "Закрыть")]

    def __init__(self, entry):
        super().__init__()
        self.entry = entry

    def compose(self):
        e = self.entry
        with Vertical(classes="dialog"):
            yield Label(f"Строка {e['index']}  ·  {e['level']}", classes="title", markup=False)
            with VerticalScroll(id="detail-body"):
                yield Static("  ·  ".join(str(e[k]) for k in ("date", "time", "source", "format")
                                         if e[k] != "N"), markup=False, classes="metadata")
                yield Label("Сообщение", classes="caption")
                yield Static(e["message"], markup=False)
                yield Label("Исходная строка с маскировкой", classes="caption")
                yield Static(e["raw"], markup=False)
            with Horizontal(classes="buttons"):
                yield Button("Закрыть  esc", id="close-detail")

    def on_mount(self):
        self.app.reveal(self)

    def on_button_pressed(self):
        self.dismiss()


class Journal(Page):
    BINDINGS = [Binding("f", "filter", "Фильтр"), Binding("enter", "details", "Подробнее", priority=True)]
    FILTERS = ("Все записи", "Ошибки и предупреждения", "Опасные")
    LIVE_LIMIT = 2000

    def __init__(self, path, live):
        super().__init__()
        self.path, self.live = path, live
        self.entries = {}
        self.counts = Counter()
        self.total = self.danger_count = self.sent = self.failed = self.filter_index = 0
        self.stop = Event()

    def compose(self):
        yield from bar("Мониторинг" if self.live else "Анализ файла")
        with Vertical(classes="journal"):
            yield Label(mask_sensitive(self.path.name), classes="title", markup=False)
            yield Static("", id="counts")
            with Horizontal(id="list-label"):
                yield Label(self.FILTERS[0], id="filter-name")
                yield Label("Чтение…", id="read-status", markup=False)
            yield Static("", id="empty", markup=False)
            yield DataTable(id="records", cursor_type="row", show_row_labels=False,
                            cursor_foreground_priority="renderable")
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_column("Строка", width=6)
        table.add_column("Время", width=12)
        table.add_column("Уровень", width=8)
        table.add_column("Сообщение", width=max(12, min(self.app.size.width, 126) - 40))
        table.focus()
        self.refresh_counts()
        self.update_empty()
        self.read_entries()

    def action_back(self):
        self.stop.set()
        super().action_back()

    def on_unmount(self):
        self.stop.set()

    @work(thread=True)
    def read_entries(self):
        worker = get_current_worker()
        dangers = load_settings()
        user_hash, enabled = load_config(NOTIFICATION_CONFIG)
        enabled = enabled and bool(notification_url())
        pending = []
        sent = failed = 0
        try:
            stream = (iterate_realtime(self.path, dangers, self.stop) if self.live
                      else iter_log_entries(self.path, dangers))
            if self.live:
                self.app.call_from_thread(self.set_status, "В эфире · ожидание строк")
            for entry in stream:
                if self.stop.is_set() or worker.is_cancelled:
                    return
                pending.append(entry)
                if enabled and entry["is_danger"]:
                    timestamp = " ".join(entry[k] for k in ("date", "time") if entry[k] != "N")
                    if self.app.send_notification(entry["level"], entry["message"], entry["source"],
                                                  timestamp, user_hash):
                        sent += 1
                    else:
                        failed += 1
                if self.live or len(pending) == 128:
                    self.app.call_from_thread(self.accept, pending, sent, failed)
                    pending = []
            if not self.stop.is_set() and not worker.is_cancelled:
                self.app.call_from_thread(self.accept, pending, sent, failed)
                self.app.call_from_thread(self.set_status, "Файл прочитан")
        except OSError as exc:
            if not self.stop.is_set() and not worker.is_cancelled:
                self.app.call_from_thread(self.set_status, mask_sensitive(str(exc)))

    def set_status(self, text):
        if self.is_mounted and not self.stop.is_set():
            self.query_one("#read-status", Label).update(text)

    def visible_entry(self, entry):
        if self.filter_index == 1:
            return entry["level"] in ("ERROR", "WARN", "CRITICAL")
        return self.filter_index == 0 or entry["is_danger"]

    def insert_row(self, table, entry):
        level = entry["level"]
        color = {"ERROR": AMBER.error, "CRITICAL": AMBER.error, "WARN": AMBER.warning,
                 "DEBUG": AMBER.secondary, "INFO": AMBER.primary}.get(level)
        message = " ".join(entry["message"].split())[:240]
        table.add_row(str(entry["index"]), Text(entry["time"] if entry["time"] != "N" else "—"),
                      Text(level if level != "N" else "—", style=color or ""),
                      Text(message, overflow="ellipsis", no_wrap=True), key=str(entry["index"]))

    def accept(self, batch, sent, failed):
        if self.stop.is_set() or not self.is_mounted:
            return
        table = self.query_one(DataTable)
        follow = self.live and table.cursor_row >= table.row_count - 1
        for entry in batch:
            if self.live and len(self.entries) == self.LIVE_LIMIT:
                old = self.entries.pop(next(iter(self.entries)))
                if self.visible_entry(old):
                    table.remove_row(str(old["index"]))
            self.entries[entry["index"]] = entry
            self.counts[entry["level"]] += 1
            self.danger_count += bool(entry["is_danger"])
            self.total += 1
            if self.visible_entry(entry):
                self.insert_row(table, entry)
        self.sent, self.failed = sent, failed
        self.refresh_counts()
        self.update_empty()
        if follow and table.row_count:
            table.move_cursor(row=table.row_count - 1, animate=False)
        if batch and self.live:
            self.set_status(f"В эфире · последние {len(self.entries)}")

    def refresh_counts(self):
        counts = Text()
        metrics = [("Строк", self.total, AMBER.foreground),
                   ("Ошибок", self.counts["ERROR"] + self.counts["CRITICAL"], AMBER.error),
                   ("Предупреждений", self.counts["WARN"], AMBER.warning),
                   ("Опасных", self.danger_count, AMBER.foreground)]
        for label, value, color in metrics:
            if counts:
                counts.append("   ")
            counts.append(f"{label} ")
            counts.append(str(value), style=color)
        if self.sent or self.failed:
            counts.append(f"   Доставлено {self.sent} / сбоев {self.failed}")
        self.query_one("#counts", Static).update(counts)

    def update_empty(self):
        empty = self.query_one("#empty", Static)
        empty.display = not self.query_one(DataTable).row_count
        if empty.display:
            empty.update("Нет записей по фильтру" if self.filter_index else
                         "Ожидание новых строк…" if self.live else "Нет записей")

    def redraw(self):
        table = self.query_one(DataTable)
        table.clear()
        for entry in self.entries.values():
            if self.visible_entry(entry):
                self.insert_row(table, entry)
        self.update_empty()
        self.refresh_counts()

    def action_filter(self):
        self.filter_index = (self.filter_index + 1) % len(self.FILTERS)
        self.query_one("#filter-name", Label).update(self.FILTERS[self.filter_index])
        self.redraw()

    def on_data_table_row_selected(self, event):
        self.show_entry(event.row_key.value)

    def action_details(self):
        table = self.query_one(DataTable)
        if table.row_count:
            self.show_entry(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)

    def show_entry(self, key):
        self.app.push_screen(Details(self.entries[int(key)]))


class Settings(Page):
    AUTO_FOCUS = "#levels"
    def compose(self):
        self.dangers = load_settings()
        user_hash, enabled = load_config(NOTIFICATION_CONFIG)
        yield from bar("Настройки")
        with VerticalScroll(classes="page"):
            yield Label("Уровни опасности", classes="title")
            yield Label("Пробел переключает отметку уровня", classes="caption")
            with Horizontal(classes="buttons"):
                yield SelectionList(*[(str(level), level, bool(value)) for level, value in self.dangers.items()],
                                    id="levels")
            with Horizontal(classes="buttons"):
                yield Button("Сохранить", variant="primary", id="save")
                yield Button("Стандартные", id="defaults")
            yield Static("", id="settings-status", markup=False)
            yield Label("Уведомления", classes="caption")
            yield Label("Включены" if enabled and notification_url() else "Выключены", id="notify-state")
            if notification_url():
                yield Input(placeholder="Хэш получателя", password=True, value=user_hash, id="recipient")
                with Horizontal(classes="buttons"):
                    yield Button("Проверить и включить", id="enable")
            else:
                yield Static(NOTIFICATION_URL_REQUIRED, markup=False)
            if enabled or notification_url():
                with Horizontal(classes="buttons"):
                    yield Button("Отключить", id="disable")
        yield Footer()

    def on_button_pressed(self, event):
        action = event.button.id
        levels = self.query_one(SelectionList)
        status = self.query_one("#settings-status", Static)
        try:
            if action == "defaults":
                levels.deselect_all()
                for level, enabled in default_dangers.items():
                    if enabled and level in self.dangers:
                        levels.select(level)
                status.update("Выбраны стандартные уровни. Нажмите «Сохранить».")
            elif action == "save":
                save_settings({level: level in levels.selected for level in self.dangers})
                status.update("Уровни сохранены.")
            elif action == "disable":
                user_hash, _ = load_config(NOTIFICATION_CONFIG)
                save_config(NOTIFICATION_CONFIG, user_hash, False)
                self.query_one("#notify-state", Label).update("Выключены")
            elif action == "enable":
                recipient = self.query_one("#recipient", Input).value.strip().upper()
                if len(recipient) < 8:
                    self.query_one("#notify-state", Label).update("Введите не менее 8 символов.")
                    return
                self.query_one("#enable", Button).disabled = True
                self.query_one("#disable", Button).disabled = True
                self.query_one("#notify-state", Label).update("Проверка соединения…")
                self.verify_recipient(recipient)
        except OSError as exc:
            status.update(str(exc))

    @work(thread=True)
    def verify_recipient(self, recipient):
        url = notification_url()
        try:
            requests.get(f"{url}/", timeout=3).raise_for_status()
            requests.post(f"{url}/send", json={"user_hash": recipient, "level": "INFO",
                          "message": "Проверка уведомлений CL-Logs"}, timeout=5).raise_for_status()
            error = ""
        except requests.RequestException as exc:
            error = str(exc)
        if not get_current_worker().is_cancelled:
            self.app.call_from_thread(self.finish_verify, recipient, error)

    def finish_verify(self, recipient, error):
        if not self.is_mounted:
            return
        if not error:
            try:
                save_config(NOTIFICATION_CONFIG, recipient, True)
            except OSError as exc:
                error = str(exc)
        self.query_one("#notify-state", Label).update(Text(error or "Включены"))
        self.query_one("#enable", Button).disabled = False
        self.query_one("#disable", Button).disabled = False


class LogConsole(App):
    TITLE = "CL-Logs"
    CSS_PATH = "console_ui.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("ctrl+q", "quit", "Выход", show=False, priority=True)]

    def __init__(self, send_notification):
        self.reveal_frame = None
        self.reveal_timer = None
        self.reveal_screen = None
        super().__init__()
        self.send_notification = send_notification
        self.register_theme(AMBER)
        self.theme = AMBER.name

    def on_mount(self):
        self.push_screen(Home())

    def get_line_filters(self):
        filters = super().get_line_filters()
        if self.reveal_frame is not None and self.screen is self.reveal_screen:
            return [*filters, self.reveal_frame]
        return filters

    def reveal(self, screen):
        if self.reveal_timer is not None:
            self.reveal_timer.stop()
        if self.animation_level != "full":
            self.reveal_frame = self.reveal_timer = self.reveal_screen = None
            return
        started = monotonic()
        self.reveal_screen = screen
        self.reveal_frame = RevealFrame(0)

        def advance():
            if self.reveal_screen is not screen:
                return
            progress = (monotonic() - started) / RevealFrame.DURATION
            if progress >= 1 or self.screen is not screen:
                self.reveal_timer.stop()
                self.reveal_frame = self.reveal_timer = self.reveal_screen = None
            else:
                self.reveal_frame = RevealFrame(progress)
            self.refresh()

        self.reveal_timer = self.set_interval(1 / 20, advance)
        self.refresh()
