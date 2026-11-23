import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
from pathlib import Path
import threading
import queue
import re
import requests
from logic.notifications import (
    NOTIFICATION_CONFIG,
    NOTIFICATION_URL_REQUIRED,
    load_config,
    notification_url,
    save_config,
)
from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime
from logic.settings import load_settings, save_settings, restoretodefaults

class LogAnalyzerApp:
    def __init__(self, root):
        self.root = root
        theme_dir = Path(__file__).resolve().parent
        for theme in ('forest-light.tcl', 'forest-dark.tcl'):
            root.tk.call('source', str(theme_dir / theme))

        self.current_theme = tk.StringVar(value="forest-light")
        self.style = ttk.Style()
        self.style.theme_use(self.current_theme.get())

        self.settings_window = None
        self.hash_window = None
        self.notify_window = None

        self.root.title("Анализатор логов")
        self.root.geometry("1400x800")

        self.dangers = load_settings()

        self.user_config_path = NOTIFICATION_CONFIG
        self.load_user_config()

        self.log_queue = queue.Queue()
        self._active_operation = None
        self._queue_callback = None
        self._closing = False
        self.realtime_running = False

        self.current_log_path = ""
        self.parsed_entries = []
        self.current_entries = []
        self.display_to_original_map = {}

        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.process_queue()
        self.apply_theme()

    def load_user_config(self):
        self.user_hash, self.notifications_enabled = load_config(self.user_config_path)

    def save_user_config(self, user_hash, enabled):
        try:
            save_config(self.user_config_path, user_hash, enabled)
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки уведомлений: {e}")
            return False
        self.user_hash = user_hash
        self.notifications_enabled = enabled
        return True

    def can_send_notifications(self):
        return bool(self.notifications_enabled and self.user_hash and notification_url())

    def setup_notifications_gui(self, *, change_hash=False):
        base_url = notification_url()
        if not base_url:
            messagebox.showinfo("Уведомления", NOTIFICATION_URL_REQUIRED)
            return False

        if self.user_hash and not change_hash:
            answer = messagebox.askyesno(
                "Настройка уведомлений",
                f"Найден сохранённый user_hash: {self.user_hash}\nИспользовать его?"
            )
            if answer:
                return self.save_user_config(self.user_hash, True)

        while True:
            new_hash = simpledialog.askstring(
                "User hash",
                "Введите ваш user_hash (или оставьте поле пустым для отмены):"
            )
            if new_hash is None or new_hash.strip() == "":
                return False

            new_hash = new_hash.strip().upper()
            if len(new_hash) < 8:
                messagebox.showerror("Ошибка", "Хэш слишком короткий (минимум 8 символов).")
                continue

            try:
                resp = requests.get(f"{base_url}/", timeout=3)
                if resp.status_code != 200:
                    messagebox.showerror("Ошибка", "Сервер недоступен. Проверьте соединение.")
                    if not messagebox.askyesno("Повторить", "Попробовать снова?"):
                        return False
                    continue

                test_data = {
                    "user_hash": new_hash,
                    "message": "🔧 Тестовая проверка системы уведомлений\n✅ Соединение установлено",
                    "level": "INFO"
                }
                response = requests.post(f"{base_url}/send", json=test_data, timeout=5)
                if response.status_code == 200:
                    user_data = response.json().get('user', {})
                    if not self.save_user_config(new_hash, True):
                        return False
                    messagebox.showinfo(
                        "Успех",
                        f"Настройка завершена!\nПользователь: {user_data.get('first_name', 'Unknown')}"
                    )
                    return True
                elif response.status_code == 404:
                    error_msg = response.json().get('error', 'User not found')
                    messagebox.showerror("Ошибка", f"Неверный user_hash: {error_msg}")
                else:
                    messagebox.showerror("Ошибка", f"Ошибка сервера: {response.status_code}")
            except requests.exceptions.ConnectionError:
                messagebox.showerror("Ошибка", "Не удалось подключиться к серверу.")
                if not messagebox.askyesno("Повторить", "Попробовать снова?"):
                    return False
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка: {str(e)}")
                if not messagebox.askyesno("Повторить", "Попробовать снова?"):
                    return False

    def send_notification(self, level, message, source, timestamp=""):
        base_url = notification_url()
        user_hash = self.user_hash
        if not self.notifications_enabled or not user_hash or not base_url:
            return False

        try:
            tg_message = f"⚠️ {level}\n📝 Сообщение: {message}"
            send_data = {
                "user_hash": user_hash,
                "message": tg_message.strip(),
                "level": level
            }
            response = requests.post(f"{base_url}/send", json=send_data, timeout=10)

            if response.status_code != 200:
                return False

            if level == "ERROR":
                email_subject = f"🚨 КРИТИЧЕСКАЯ ОШИБКА - {timestamp}"
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
                response = requests.post(f"{base_url}/send_email", json=email_data, timeout=10)
                return response.status_code == 200

            return True
        except Exception:
            return False

    def open_notification_settings(self):
        if self.notify_window and self.notify_window.winfo_exists():
            self.notify_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.notify_window = win
        win.title("Управление уведомлениями")
        win.geometry("400x250")
        win.resizable(False, False)

        if self.current_theme.get() == "forest-light":
            win.configure(bg='#f0f0f0')
        else:
            win.configure(bg='#2d2d2d')

        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        available = bool(notification_url())
        status = "Включены" if self.can_send_notifications() else "Отключены"
        ttk.Label(main, text=f"Статус: {status}").pack(anchor=tk.W, pady=5)
        if not available:
            ttk.Label(main, text=NOTIFICATION_URL_REQUIRED, wraplength=360).pack(anchor=tk.W, pady=5)
        if self.user_hash:
            ttk.Label(main, text=f"Хэш: {self.user_hash}").pack(anchor=tk.W, pady=5)

        def enable():
            if self.setup_notifications_gui():
                self.update_stats_display()
                messagebox.showinfo("Уведомления", "Уведомления включены.")
            win.destroy()

        def disable():
            if self.save_user_config(self.user_hash, False):
                self.update_stats_display()
                messagebox.showinfo("Уведомления", "Уведомления отключены.")
                win.destroy()

        def change_hash():
            if self.setup_notifications_gui(change_hash=True):
                self.update_stats_display()
                messagebox.showinfo("Успех", "Хэш обновлён.")
            win.destroy()

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=10)
        setup_state = 'normal' if available else 'disabled'

        if self.notifications_enabled:
            ttk.Button(btn_frame, text="Отключить", command=disable).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Сменить хэш", command=change_hash,
                       state=setup_state).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Button(btn_frame, text="Включить", command=enable,
                       state=setup_state).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Закрыть", command=win.destroy).pack(side=tk.RIGHT, padx=5)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def create_widgets(self):
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_panel = ttk.Frame(main_container, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_panel.pack_propagate(False)

        center_panel = ttk.Frame(main_container)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_panel = ttk.Frame(main_container, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)

        list_frame = ttk.LabelFrame(left_panel, text="Записи лога")
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_controls = ttk.Frame(list_frame)
        list_controls.pack(fill=tk.X, padx=5, pady=5)

        self.filter_var = tk.StringVar(value="Все")
        filter_combo = ttk.Combobox(list_controls, textvariable=self.filter_var,
                                    values=["Все", "Только опасные", "Только безопасные"],
                                    state="readonly", width=15)
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind("<<ComboboxSelected>>", self.filter_entries)

        self.count_label = ttk.Label(list_controls, text="0/0")
        self.count_label.pack(side=tk.RIGHT)

        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.entries_listbox = tk.Listbox(list_container, font=("Courier New", 9))
        self.entries_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.entries_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.entries_listbox.configure(yscrollcommand=scrollbar.set)
        self.entries_listbox.bind('<<ListboxSelect>>', self.on_entry_select)

        detail_frame = ttk.LabelFrame(center_panel, text="Детали записи")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.detail_text = scrolledtext.ScrolledText(detail_frame, wrap=tk.WORD,
                                                     font=("Courier New", 10),
                                                     height=15, state='disabled')
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        raw_frame = ttk.LabelFrame(center_panel, text="Исходный текст")
        raw_frame.pack(fill=tk.BOTH, expand=True)
        self.raw_text = scrolledtext.ScrolledText(raw_frame, wrap=tk.WORD,
                                                  font=("Courier New", 10),
                                                  height=10, state='disabled')
        self.raw_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(right_panel, text="Анализатор логов", font=("Arial", 12, "bold")).pack(pady=10)

        file_frame = ttk.LabelFrame(right_panel, text="Файл лога")
        file_frame.pack(fill=tk.X, pady=5)
        self.path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.path_var, state='readonly').pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(file_frame, text="Выбрать файл", command=self.select_log_file).pack(fill=tk.X, padx=5, pady=(0, 5))

        action_frame = ttk.LabelFrame(right_panel, text="Действия")
        action_frame.pack(fill=tk.X, pady=5)
        btn_width = 23
        self.realtime_btn = ttk.Button(action_frame, text="Режим реального времени",
                                       width=btn_width, command=self.start_realtime)
        self.realtime_btn.pack(pady=3)
        self.analyze_btn = ttk.Button(action_frame, text="Анализ лога",
                                      width=btn_width, command=self.analyze_log)
        self.analyze_btn.pack(pady=3)
        self.stop_btn = ttk.Button(action_frame, text="Остановить мониторинг",
                                   width=btn_width, command=self.stop_realtime, state='disabled')
        self.stop_btn.pack(pady=3)
        ttk.Button(action_frame, text="Очистить список", width=btn_width,
                   command=self.clear_entries).pack(pady=3)

        settings_frame = ttk.LabelFrame(right_panel, text="Настройки")
        settings_frame.pack(fill=tk.X, pady=5)
        ttk.Button(settings_frame, text="Настройки анализа", width=btn_width,
                   command=self.open_settings).pack(pady=3)
        ttk.Button(settings_frame, text="Настройки hash кода", width=btn_width,
                   command=self.open_hash_settings).pack(pady=3)
        ttk.Button(settings_frame, text="Уведомления", width=btn_width,
                   command=self.open_notification_settings).pack(pady=3)
        ttk.Button(settings_frame, text="Переключить тему", width=btn_width,
                   command=self.toggle_theme).pack(pady=3)

        stats_frame = ttk.LabelFrame(right_panel, text="Статистика")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD,
                                                    font=("Arial", 9), height=8, state='disabled')
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Готов к работе")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def open_hash_settings(self):
        if self.hash_window and self.hash_window.winfo_exists():
            self.hash_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.hash_window = win
        win.title("Настройки hash кода")
        win.geometry("400x200")
        win.resizable(False, False)
        if self.current_theme.get() == "forest-light":
            win.configure(bg='#f0f0f0')
        else:
            win.configure(bg='#2d2d2d')

        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main, text="User hash:", font=("Arial", 10)).pack(anchor=tk.W, pady=5)
        hash_var = tk.StringVar(value=self.user_hash)
        entry = ttk.Entry(main, textvariable=hash_var, width=40)
        entry.pack(fill=tk.X, pady=5)

        def save():
            new_hash = hash_var.get().strip()
            if not self.save_user_config(new_hash, bool(new_hash) and self.notifications_enabled):
                return
            self.update_stats_display()
            messagebox.showinfo("Сохранено", "User hash сохранён в user_config.json")
            win.destroy()
            self.hash_window = None

        def cancel():
            win.destroy()
            self.hash_window = None

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Сохранить", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=cancel).pack(side=tk.RIGHT, padx=5)
        win.protocol("WM_DELETE_WINDOW", cancel)

    def toggle_theme(self):
        if self.current_theme.get() == "forest-light":
            self.current_theme.set("forest-dark")
        else:
            self.current_theme.set("forest-light")
        self.apply_theme()
        if self.settings_window and self.settings_window.winfo_exists():
            self.update_settings_theme()
        self.status_var.set(f"Тема изменена на {'тёмную' if self.current_theme.get() == 'forest-dark' else 'светлую'}")

    def apply_theme(self):
        self.style.theme_use(self.current_theme.get())
        if self.current_theme.get() == "forest-dark":
            bg, fg, select_bg, select_fg, highlight = '#2d2d2d', '#ffffff', '#4a4a4a', '#ffffff', '#3a3a3a'
        else:
            bg, fg, select_bg, select_fg, highlight = '#ffffff', '#000000', '#0078d7', '#ffffff', '#ffff99'
        self.entries_listbox.configure(bg=bg, fg=fg, selectbackground=select_bg, selectforeground=select_fg)
        self.detail_text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.raw_text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.stats_text.configure(bg=bg, fg=fg)
        self.refresh_listbox_colors()
        self.update_highlight_tags(highlight)

    def update_settings_theme(self):
        if not self.settings_window or not self.settings_window.winfo_exists():
            return
        ttk.Style(self.settings_window).theme_use(self.current_theme.get())
        bg = '#f0f0f0' if self.current_theme.get() == "forest-light" else '#2d2d2d'
        self.settings_window.configure(bg=bg)

    def update_highlight_tags(self, highlight_bg):
        self.detail_text.tag_configure("danger", background=highlight_bg)
        self.raw_text.tag_configure("danger", background=highlight_bg)
        selection = self.entries_listbox.curselection()
        if selection:
            display_index = selection[0]
            if display_index in self.display_to_original_map:
                orig = self.display_to_original_map[display_index]
                if orig < len(self.parsed_entries) and self.parsed_entries[orig]["is_danger"]:
                    self.display_entry_details(self.parsed_entries[orig], display_index + 1)

    def refresh_listbox_colors(self):
        for i in range(self.entries_listbox.size()):
            if i in self.display_to_original_map:
                orig = self.display_to_original_map[i]
                if orig < len(self.parsed_entries):
                    danger = self.parsed_entries[orig]["is_danger"]
                    color = "#ff6b6b" if danger else "#6bff6b"
                    if self.current_theme.get() != "forest-dark":
                        color = "red" if danger else "green"
                    self.entries_listbox.itemconfig(i, {'fg': color})

    def select_log_file(self):
        path = filedialog.askopenfilename(title="Выберите файл лога",
                                          filetypes=[("Лог файлы", "*.log"), ("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if path:
            self.current_log_path = path
            self.path_var.set(path)
            self.status_var.set(f"Выбран файл: {Path(path).name}")

    def start_realtime(self):
        self._start_log_operation(
            self.realtime_monitoring,
            "Мониторинг в реальном времени запущен...",
            realtime=True,
        )

    def realtime_monitoring(self, operation, path, dangers):
        try:
            for entry in iterate_realtime(path, dangers, stop_event=operation):
                if operation.is_set():
                    return
                self.log_queue.put((operation, "entry", entry))
        except Exception as e:
            self.log_queue.put((operation, "error", str(e)))
        else:
            self.log_queue.put((operation, "realtime_finished", None))

    def stop_realtime(self):
        if not self.realtime_running:
            return
        self._active_operation.set()
        self._finish_log_operation()
        self.status_var.set("Мониторинг остановлен")

    def _finish_log_operation(self):
        self._active_operation = None
        self.realtime_running = False
        self.realtime_btn.config(state='normal')
        self.analyze_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

    def analyze_log(self):
        self._start_log_operation(self.run_analysis, "Выполняется анализ лога...")

    def _start_log_operation(self, worker, status, *, realtime=False):
        if self._closing or self._active_operation is not None:
            return
        if not self.current_log_path:
            messagebox.showwarning("Внимание", "Сначала выберите файл лога!")
            return
        operation = threading.Event()
        self._active_operation = operation
        self.realtime_running = realtime
        self.realtime_btn.config(state='disabled')
        self.analyze_btn.config(state='disabled')
        self.stop_btn.config(state='normal' if realtime else 'disabled')
        self.clear_entries()
        self.status_var.set(status)
        try:
            threading.Thread(
                target=worker,
                args=(operation, self.current_log_path, self.dangers.copy()),
                daemon=True,
            ).start()
        except RuntimeError as e:
            self.log_queue.put((operation, "error", str(e)))

    def run_analysis(self, operation, path, dangers):
        try:
            entries, danger_lines = analyze_log(path, dangers)
            for entry in entries:
                if operation.is_set():
                    return
                self.log_queue.put((operation, "entry", entry))
            self.log_queue.put((operation, "stats", {
                'total': len(entries),
                'danger': len(danger_lines),
                'danger_lines': danger_lines
            }))
        except Exception as e:
            self.log_queue.put((operation, "error", str(e)))

    def open_settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Настройки анализатора")
        self.settings_window.geometry("500x600")
        bg = '#ffffff' if self.current_theme.get() == "forest-light" else '#313131'
        self.settings_window.configure(bg=bg)
        ttk.Style(self.settings_window).theme_use(self.current_theme.get())

        truedangers = [lvl for lvl in self.dangers if self.dangers[lvl]]
        ttk.Label(self.settings_window, text=f"Сейчас система считает нежелательными:\n{', '.join(truedangers)}",
                  font=("Arial", 10)).pack(pady=10)

        settings_frame = ttk.LabelFrame(self.settings_window, text="Настройки уровней")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        check_vars = {}
        for lvl in self.dangers:
            var = tk.BooleanVar(value=self.dangers[lvl])
            check_vars[lvl] = var
            ttk.Checkbutton(settings_frame, text=lvl, variable=var).pack(anchor=tk.W, padx=20, pady=5)

        button_frame = ttk.Frame(self.settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_and_close():
            for lvl in self.dangers:
                self.dangers[lvl] = check_vars[lvl].get()
            save_settings(self.dangers)
            self.update_stats_display()
            if self.settings_window:
                self.settings_window.destroy()
            self.settings_window = None
            messagebox.showinfo("Успех", "Настройки сохранены!")

        def restore_defaults():
            self.dangers = restoretodefaults()
            save_settings(self.dangers)
            self.update_stats_display()
            if self.settings_window:
                self.settings_window.destroy()
            self.settings_window = None
            messagebox.showinfo("Успех", "Настройки восстановлены по умолчанию!")

        def on_closing():
            if self.settings_window:
                self.settings_window.destroy()
            self.settings_window = None

        self.settings_window.protocol("WM_DELETE_WINDOW", on_closing)
        ttk.Button(button_frame, text="Сохранить", command=save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="По умолчанию", command=restore_defaults).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=on_closing).pack(side=tk.RIGHT, padx=5)

    def process_queue(self):
        self._queue_callback = None
        delay = 1
        for _ in range(100):
            if self._closing:
                return
            try:
                operation, msg_type, data = self.log_queue.get_nowait()
            except queue.Empty:
                delay = 100
                break
            if operation is not self._active_operation:
                continue
            if msg_type == "entry":
                self.add_entry(data)
            elif msg_type == "error":
                self._finish_log_operation()
                self.status_var.set(f"Ошибка: {data}")
                messagebox.showerror("Ошибка", data)
            elif msg_type == "stats":
                self._finish_log_operation()
                self.update_stats_display(data)
            elif msg_type == "realtime_finished":
                self._finish_log_operation()
                self.status_var.set("Мониторинг завершен")
        if not self._closing:
            self._queue_callback = self.root.after(delay, self.process_queue)

    def close(self):
        self._closing = True
        if self._active_operation is not None:
            self._active_operation.set()
            self._active_operation = None
        if self._queue_callback is not None:
            self.root.after_cancel(self._queue_callback)
        self.root.destroy()

    def add_entry(self, entry):
        self.parsed_entries.append(entry)
        filter_type = self.filter_var.get()
        should_display = True
        if filter_type == "Только опасные" and not entry["is_danger"]:
            should_display = False
        elif filter_type == "Только безопасные" and entry["is_danger"]:
            should_display = False
        if should_display:
            self.current_entries.append(entry)
            self.display_to_original_map[len(self.current_entries)-1] = len(self.parsed_entries)-1
            list_text = self.format_entry_for_list(entry, len(self.current_entries))
            self.entries_listbox.insert(tk.END, list_text)
            color = "#ff6b6b" if entry["is_danger"] else "#6bff6b"
            if self.current_theme.get() != "forest-dark":
                color = "red" if entry["is_danger"] else "green"
            self.entries_listbox.itemconfig(tk.END, {'fg': color})
        self.update_count_label()

        if entry["is_danger"] and self.can_send_notifications():
            timestamp = f"{entry['date']} {entry['time']}" if entry["date"] != "N" else entry["time"]
            threading.Thread(target=self.send_notification,
                             args=(entry["level"], entry["message"], entry["source"], timestamp),
                             daemon=True).start()

    def format_entry_for_list(self, entry, display_index):
        time_display = entry["time"] if entry["date"] == "N" else entry["time"]
        if len(time_display) > 15:
            time_display = time_display[:12] + "..."
        icon = "⚠" if entry["is_danger"] else "✓"
        return f"{icon} #{display_index:3d} | {time_display:15s} | {entry['level']:8s}"

    def on_entry_select(self, event):
        sel = self.entries_listbox.curselection()
        if not sel:
            return
        display_index = sel[0]
        if display_index in self.display_to_original_map:
            orig = self.display_to_original_map[display_index]
            if orig < len(self.parsed_entries):
                self.display_entry_details(self.parsed_entries[orig], display_index+1)

    def display_entry_details(self, entry, display_index=None):
        self.detail_text.config(state='normal')
        self.raw_text.config(state='normal')
        self.detail_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)

        idx = display_index if display_index is not None else entry['index']
        detail = f"Запись #{idx}\n" + "="*40 + "\n\n"
        detail += f"Уровень:       {entry['level']}\n"
        if entry["date"] != "N":
            detail += f"Дата:          {entry['date']}\nВремя:         {entry['time']}\n"
        else:
            detail += f"Время:         {entry['time']}\n"
        detail += f"Источник:      {entry['source']}\nФормат записи: {entry['format']}\n"
        detail += "Статус:        ⚠ ОПАСНАЯ ЗАПИСЬ\n" if entry["is_danger"] else "Статус:        ✓ Нормальная\n"
        detail += "\nСообщение:\n" + "-"*40 + "\n" + entry['message'] + "\n"
        detail += "\n" + "="*40 + f"\nСтрока в файле: {entry['index']}\nДлина сообщения: {len(entry['message'])} символов\n"

        self.detail_text.insert(1.0, detail)
        self.raw_text.insert(1.0, entry['raw'])

        if entry["is_danger"]:
            highlight = "#ffff99" if self.current_theme.get() == "forest-light" else "#3a3a3a"
            self.detail_text.tag_configure("danger", background=highlight)
            self.detail_text.tag_add("danger", "1.0", tk.END)
            self.raw_text.tag_configure("danger", background=highlight)
            self.raw_text.tag_add("danger", "1.0", tk.END)

        self.detail_text.config(state='disabled')
        self.raw_text.config(state='disabled')

    def filter_entries(self, event=None):
        filter_type = self.filter_var.get()
        self.entries_listbox.delete(0, tk.END)
        self.current_entries.clear()
        self.display_to_original_map.clear()
        display_index = 0
        for orig_idx, entry in enumerate(self.parsed_entries):
            show = True
            if filter_type == "Только опасные" and not entry["is_danger"]:
                show = False
            elif filter_type == "Только безопасные" and entry["is_danger"]:
                show = False
            if show:
                self.current_entries.append(entry)
                self.display_to_original_map[display_index] = orig_idx
                list_text = self.format_entry_for_list(entry, display_index+1)
                self.entries_listbox.insert(tk.END, list_text)
                color = "#ff6b6b" if entry["is_danger"] else "#6bff6b"
                if self.current_theme.get() != "forest-dark":
                    color = "red" if entry["is_danger"] else "green"
                self.entries_listbox.itemconfig(tk.END, {'fg': color})
                display_index += 1
        self.update_count_label()

    def clear_entries(self):
        self.parsed_entries.clear()
        self.current_entries.clear()
        self.display_to_original_map.clear()
        self.entries_listbox.delete(0, tk.END)
        self.detail_text.config(state='normal')
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.config(state='disabled')
        self.raw_text.config(state='normal')
        self.raw_text.delete(1.0, tk.END)
        self.raw_text.config(state='disabled')
        self.update_count_label()
        self.status_var.set("Список записей очищен")

    def update_count_label(self):
        total = len(self.parsed_entries)
        filtered = len(self.current_entries)
        self.count_label.config(text=f"{filtered}/{total}" if filtered != total else f"{total} зап.")

    def update_stats_display(self, stats_data=None):
        self.stats_text.config(state='normal')
        self.stats_text.delete(1.0, tk.END)
        if stats_data:
            stats = f"Статистика анализа:\n{'='*25}\nВсего записей: {stats_data['total']}\nОпасных: {stats_data['danger']}\nБезопасных: {stats_data['total'] - stats_data['danger']}\n"
            stats += f"Процент опасных: {(stats_data['danger']/stats_data['total']*100 if stats_data['total']>0 else 0):.1f}%\n"
            if stats_data['danger_lines']:
                stats += "\nОпасные строки:\n" + ', '.join(map(str, stats_data['danger_lines'])) + "\n"
            self.stats_text.insert(1.0, stats)
            self.status_var.set(f"Анализ завершен. Обработано {stats_data['total']} записей")
        else:
            truedangers = [lvl for lvl in self.dangers if self.dangers[lvl]]
            text = f"Текущие настройки:\n{'='*25}\nОпасные уровни:\n"
            text += '\n'.join(f"• {lvl}" for lvl in truedangers) if truedangers else "не заданы\n"
            if self.parsed_entries:
                danger_cnt = sum(1 for e in self.parsed_entries if e["is_danger"])
                text += f"\nТекущая сессия:\nВсего записей: {len(self.parsed_entries)}\nОпасных: {danger_cnt}\nБезопасных: {len(self.parsed_entries)-danger_cnt}\n"
                if len(self.parsed_entries):
                    text += f"Процент опасных: {(danger_cnt/len(self.parsed_entries)*100):.1f}%\n"
            if self.can_send_notifications():
                text += f"\n🔔 Уведомления: ВКЛ ({self.user_hash[:8]}...)"
            else:
                text += "\n🔔 Уведомления: ВЫКЛ"
                if not notification_url():
                    text += f". {NOTIFICATION_URL_REQUIRED}"
            self.stats_text.insert(1.0, text)
        self.stats_text.config(state='disabled')


def main():
    root = tk.Tk()
    app = LogAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
