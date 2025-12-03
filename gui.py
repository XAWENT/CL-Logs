import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import os
from pathlib import Path
import threading
import queue
import re

# Импорт модулей из вашего кода анализа
from logic.onetime_logic import analyze_log
from logic.realtime_logic import iterate_realtime
from logic.settings import load_settings, save_settings, restoretodefaults

class LogAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Анализатор логов")
        self.root.geometry("1400x800")
        
        # Загружаем настройки
        self.dangers = load_settings()
        
        # Очередь для обмена данными между потоками
        self.log_queue = queue.Queue()
        
        # Флаг для остановки реального времени
        self.realtime_running = False
        
        # Переменные для хранения данных
        self.current_log_path = ""
        self.parsed_entries = []  # Все распарсенные записи
        self.current_entries = []  # Текущие отфильтрованные записи
        self.display_to_original_map = {}  # Карта отображаемых индексов к оригинальным
        
        # Создаем интерфейс
        self.create_widgets()
        
        # Запускаем обработчик очереди
        self.process_queue()
    
    def create_widgets(self):
        """Создает виджеты интерфейса"""
        
        # Главный контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель - упрощенный список записей
        left_panel = ttk.Frame(main_container, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # Центральная панель - детальный просмотр
        center_panel = ttk.Frame(main_container)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Правая панель - управление и настройки
        right_panel = ttk.Frame(main_container, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # ===== ЛЕВАЯ ПАНЕЛЬ (Упрощенный список записей) =====
        
        # Заголовок списка
        list_frame = ttk.LabelFrame(left_panel, text="Записи лога")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Панель управления списком
        list_controls = ttk.Frame(list_frame)
        list_controls.pack(fill=tk.X, padx=5, pady=5)
        
        self.filter_var = tk.StringVar(value="Все")
        filter_combo = ttk.Combobox(list_controls, textvariable=self.filter_var, 
                                   values=["Все", "Только опасные", "Только безопасные"],
                                   state="readonly", width=15)
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind("<<ComboboxSelected>>", self.filter_entries)
        
        # Счетчик записей
        count_label = ttk.Label(list_controls, text="0/0")
        count_label.pack(side=tk.RIGHT)
        self.count_label = count_label
        
        # Список записей с прокруткой
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Список записей (только номер, время и тип)
        self.entries_listbox = tk.Listbox(list_container, font=("Courier New", 9))
        self.entries_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Скроллбар для списка
        list_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, 
                                      command=self.entries_listbox.yview)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.entries_listbox.configure(yscrollcommand=list_scrollbar.set)
        
        # Привязываем выбор записи
        self.entries_listbox.bind('<<ListboxSelect>>', self.on_entry_select)
        
        # ===== ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (Детальный просмотр) =====
        
        # Верхняя часть - детали выбранной записи
        detail_frame = ttk.LabelFrame(center_panel, text="Детали записи")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Текстовое поле для детального просмотра
        self.detail_text = scrolledtext.ScrolledText(detail_frame, 
                                                    wrap=tk.WORD,
                                                    font=("Courier New", 10),
                                                    height=15)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Нижняя часть - исходный текст строки
        raw_frame = ttk.LabelFrame(center_panel, text="Исходный текст")
        raw_frame.pack(fill=tk.BOTH, expand=True)
        
        self.raw_text = scrolledtext.ScrolledText(raw_frame, 
                                                 wrap=tk.WORD,
                                                 font=("Courier New", 10),
                                                 height=10)
        self.raw_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ===== ПРАВАЯ ПАНЕЛЬ (Управление) =====
        
        # Заголовок
        title_label = ttk.Label(right_panel, text="Анализатор логов", 
                               font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # Выбор файла
        file_frame = ttk.LabelFrame(right_panel, text="Файл лога")
        file_frame.pack(fill=tk.X, pady=5)
        
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(file_frame, textvariable=self.path_var, state='readonly')
        path_entry.pack(fill=tk.X, padx=5, pady=5)
        
        browse_btn = ttk.Button(file_frame, text="Выбрать файл", 
                               command=self.select_log_file)
        browse_btn.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Меню действий
        action_frame = ttk.LabelFrame(right_panel, text="Действия")
        action_frame.pack(fill=tk.X, pady=5)
        
        # Кнопки действий
        btn_width = 23
        
        self.realtime_btn = ttk.Button(action_frame, text="Режим реального времени", 
                                      width=btn_width, command=self.start_realtime)
        self.realtime_btn.pack(pady=3)
        
        self.analyze_btn = ttk.Button(action_frame, text="Анализ лога", 
                                     width=btn_width, command=self.analyze_log)
        self.analyze_btn.pack(pady=3)
        
        self.stop_btn = ttk.Button(action_frame, text="Остановить мониторинг", 
                                  width=btn_width, command=self.stop_realtime,
                                  state='disabled')
        self.stop_btn.pack(pady=3)
        
        clear_btn = ttk.Button(action_frame, text="Очистить список", 
                              width=btn_width, command=self.clear_entries)
        clear_btn.pack(pady=3)
        
        # Настройки
        settings_frame = ttk.LabelFrame(right_panel, text="Настройки")
        settings_frame.pack(fill=tk.X, pady=5)
        
        self.settings_btn = ttk.Button(settings_frame, text="Настройки анализа", 
                                      width=btn_width, command=self.open_settings)
        self.settings_btn.pack(pady=5)
        
        # Статистика
        stats_frame = ttk.LabelFrame(right_panel, text="Статистика")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=8,
                                                   font=("Arial", 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.stats_text.config(state='disabled')
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def select_log_file(self):
        """Выбор файла лога"""
        file_path = filedialog.askopenfilename(
            title="Выберите файл лога",
            filetypes=[("Лог файлы", "*.log"), ("Текстовые файлы", "*.txt"), 
                      ("Все файлы", "*.*")]
        )
        
        if file_path:
            self.current_log_path = file_path
            self.path_var.set(file_path)
            self.status_var.set(f"Выбран файл: {Path(file_path).name}")
    
    def start_realtime(self):
        """Запуск мониторинга в реальном времени"""
        if not self.current_log_path:
            messagebox.showwarning("Внимание", "Сначала выберите файл лога!")
            return
        
        self.realtime_running = True
        self.realtime_btn.config(state='disabled')
        self.analyze_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # Очищаем предыдущие записи
        self.parsed_entries.clear()
        self.current_entries.clear()
        self.display_to_original_map.clear()
        self.entries_listbox.delete(0, tk.END)
        self.detail_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)
        
        self.status_var.set("Мониторинг в реальном времени запущен...")
        
        # Запуск в отдельном потоке
        thread = threading.Thread(target=self.realtime_monitoring, daemon=True)
        thread.start()
    
    def realtime_monitoring(self):
        """Мониторинг в реальном времени (в отдельном потоке)"""
        try:
            for entry in iterate_realtime(self.current_log_path, self.dangers):
                # Помещаем запись в очередь для обработки в основном потоке
                self.log_queue.put(("realtime_entry", entry))
                
                if not self.realtime_running:
                    break
                    
        except Exception as e:
            self.log_queue.put(("error", str(e)))
    
    def stop_realtime(self):
        """Остановка мониторинга"""
        self.realtime_running = False
        self.realtime_btn.config(state='normal')
        self.analyze_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_var.set("Мониторинг остановлен")
    
    def analyze_log(self):
        """Анализ лога"""
        if not self.current_log_path:
            messagebox.showwarning("Внимание", "Сначала выберите файл лога!")
            return
        
        # Очищаем предыдущие записи
        self.parsed_entries.clear()
        self.current_entries.clear()
        self.display_to_original_map.clear()
        self.entries_listbox.delete(0, tk.END)
        self.detail_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)
        
        self.status_var.set("Выполняется анализ лога...")
        
        # Запуск анализа в отдельном потоке
        thread = threading.Thread(target=self.run_analysis, daemon=True)
        thread.start()
    
    def run_analysis(self):
        """Запуск анализа (в отдельном потоке)"""
        try:
            entries, danger_lines = analyze_log(self.current_log_path, self.dangers)
            
            # Отправляем все записи в очередь
            for entry in entries:
                self.log_queue.put(("analysis_entry", entry))
            
            # Статистика
            self.log_queue.put(("stats", {
                'total': len(entries),
                'danger': len([e for e in entries if e["is_danger"]]),
                'danger_lines': danger_lines
            }))
                
        except Exception as e:
            self.log_queue.put(("error", str(e)))
    
    def open_settings(self):
        """Открытие настроек"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки анализатора")
        settings_window.geometry("500x600")
        
        # Получаем текущие опасные уровни
        truedangers = [lvl for lvl in self.dangers if self.dangers[lvl]]
        
        # Информация
        info_label = ttk.Label(settings_window, 
                              text=f"Сейчас система считает нежелательными:\n{', '.join(truedangers)}",
                              font=("Arial", 10))
        info_label.pack(pady=10)
        
        # Фрейм для настроек
        settings_frame = ttk.LabelFrame(settings_window, text="Настройки уровней")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Переменные для чекбоксов
        check_vars = {}
        
        # Создаем чекбоксы для каждого уровня
        for lvl in self.dangers:
            var = tk.BooleanVar(value=self.dangers[lvl])
            check_vars[lvl] = var
            
            check = ttk.Checkbutton(settings_frame, text=lvl, variable=var)
            check.pack(anchor=tk.W, padx=20, pady=5)
        
        # Фрейм для кнопок
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_and_close():
            for lvl in self.dangers:
                self.dangers[lvl] = check_vars[lvl].get()
            
            save_settings(self.dangers)
            self.update_stats_display()
            settings_window.destroy()
            messagebox.showinfo("Успех", "Настройки сохранены!")
        
        def restore_defaults():
            self.dangers = restoretodefaults()
            save_settings(self.dangers)
            self.update_stats_display()
            settings_window.destroy()
            messagebox.showinfo("Успех", "Настройки восстановлены по умолчанию!")
        
        # Кнопки
        save_btn = ttk.Button(button_frame, text="Сохранить", command=save_and_close)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        default_btn = ttk.Button(button_frame, text="По умолчанию", command=restore_defaults)
        default_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="Отмена", command=settings_window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
    
    def process_queue(self):
        """Обработка очереди сообщений"""
        try:
            while True:
                msg_type, data = self.log_queue.get_nowait()
                
                if msg_type in ["realtime_entry", "analysis_entry"]:
                    self.add_entry(data)
                elif msg_type == "error":
                    self.status_var.set(f"Ошибка: {data}")
                    messagebox.showerror("Ошибка", str(data))
                elif msg_type == "stats":
                    self.update_stats_display(data)
                    
        except queue.Empty:
            pass
        
        # Повторяем через 100 мс
        self.root.after(100, self.process_queue)
    
    def add_entry(self, entry):
        """Добавление записи в список"""
        self.parsed_entries.append(entry)
        
        # Добавляем запись в текущий отфильтрованный список, если соответствует фильтру
        should_display = True
        filter_type = self.filter_var.get()
        
        if filter_type == "Только опасные" and not entry["is_danger"]:
            should_display = False
        elif filter_type == "Только безопасные" and entry["is_danger"]:
            should_display = False
        
        if should_display:
            self.current_entries.append(entry)
            self.display_to_original_map[len(self.current_entries) - 1] = len(self.parsed_entries) - 1
            
            # Форматируем строку для списка
            list_text = self.format_entry_for_list(entry, len(self.current_entries))
            
            # Добавляем в список
            self.entries_listbox.insert(tk.END, list_text)
            
            # Устанавливаем цвет строки
            color = "red" if entry["is_danger"] else "green"
            self.entries_listbox.itemconfig(tk.END, {'fg': color})
        
        # Обновляем статистику
        self.update_count_label()
    
    def format_entry_for_list(self, entry, display_index):
        """Форматирует запись для отображения в списке"""
        # Форматируем время
        if entry["date"] != "N":
            time_display = f"{entry['time']}"  # Только время без даты
        else:
            time_display = entry["time"]
        
        # Обрезаем время если слишком длинное
        if len(time_display) > 15:
            time_display = time_display[:12] + "..."
        
        # Определяем иконку
        icon = "⚠" if entry["is_danger"] else "✓"
        
        # Формируем строку для списка
        return f"{icon} #{display_index:3d} | {time_display:15s} | {entry['level']:8s}"
    
    def on_entry_select(self, event):
        """Обработка выбора записи из списка"""
        selection = self.entries_listbox.curselection()
        if not selection:
            return
        
        display_index = selection[0]
        
        # Получаем оригинальный индекс через карту
        if display_index in self.display_to_original_map:
            original_index = self.display_to_original_map[display_index]
            if original_index < len(self.parsed_entries):
                entry = self.parsed_entries[original_index]
                self.display_entry_details(entry, display_index + 1)
    
    def display_entry_details(self, entry, display_index=None):
        """Отображение деталей выбранной записи"""
        # Очищаем поля
        self.detail_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)
        
        # Используем display_index если передан, иначе индекс из записи
        entry_index = display_index if display_index is not None else entry['index']
        
        # Форматируем детали записи
        detail_text = f"Запись #{entry_index}\n"
        detail_text += "=" * 40 + "\n\n"
        
        # Основная информация
        detail_text += f"Уровень:       {entry['level']}\n"
        
        if entry["date"] != "N":
            detail_text += f"Дата:          {entry['date']}\n"
            detail_text += f"Время:         {entry['time']}\n"
        else:
            detail_text += f"Время:         {entry['time']}\n"
        
        detail_text += f"Источник:      {entry['source']}\n"
        detail_text += f"Формат записи: {entry['format']}\n"
        
        # Статус опасности
        if entry["is_danger"]:
            detail_text += f"Статус:        ⚠ ОПАСНАЯ ЗАПИСЬ\n"
        else:
            detail_text += f"Статус:        ✓ Нормальная\n"
        
        detail_text += "\nСообщение:\n"
        detail_text += "-" * 40 + "\n"
        detail_text += entry['message'] + "\n"
        
        # Дополнительная информация
        detail_text += "\n" + "=" * 40 + "\n"
        detail_text += f"Строка в файле: {entry['index']}\n"
        detail_text += f"Длина сообщения: {len(entry['message'])} символов\n"
        
        # Вставляем в поле деталей
        self.detail_text.insert(1.0, detail_text)
        
        # Отображаем исходный текст
        self.raw_text.insert(1.0, entry['raw'])
        
        # Подсвечиваем опасные записи
        if entry["is_danger"]:
            self.detail_text.tag_configure("danger", background="lightyellow")
            self.detail_text.tag_add("danger", "1.0", tk.END)
            
            # Также подсвечиваем в raw тексте
            self.raw_text.tag_configure("danger", background="lightyellow")
            self.raw_text.tag_add("danger", "1.0", tk.END)
    
    def filter_entries(self, event=None):
        """Фильтрация записей по выбранному критерию"""
        filter_type = self.filter_var.get()
        
        # Очищаем список и карту
        self.entries_listbox.delete(0, tk.END)
        self.current_entries.clear()
        self.display_to_original_map.clear()
        
        # Применяем фильтр и заполняем списки
        display_index = 0
        for original_index, entry in enumerate(self.parsed_entries):
            should_display = True
            
            if filter_type == "Только опасные" and not entry["is_danger"]:
                should_display = False
            elif filter_type == "Только безопасные" and entry["is_danger"]:
                should_display = False
            
            if should_display:
                self.current_entries.append(entry)
                self.display_to_original_map[display_index] = original_index
                
                # Форматируем и добавляем в список
                list_text = self.format_entry_for_list(entry, display_index + 1)
                self.entries_listbox.insert(tk.END, list_text)
                
                # Устанавливаем цвет
                color = "red" if entry["is_danger"] else "green"
                self.entries_listbox.itemconfig(tk.END, {'fg': color})
                
                display_index += 1
        
        self.update_count_label()
    
    def clear_entries(self):
        """Очистка всех записей"""
        self.parsed_entries.clear()
        self.current_entries.clear()
        self.display_to_original_map.clear()
        self.entries_listbox.delete(0, tk.END)
        self.detail_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)
        self.update_count_label()
        self.status_var.set("Список записей очищен")
    
    def update_count_label(self):
        """Обновление счетчика записей"""
        total = len(self.parsed_entries)
        filtered = len(self.current_entries)
        danger = len([e for e in self.parsed_entries if e["is_danger"]])
        
        if filtered == total:
            self.count_label.config(text=f"{total} зап.")
        else:
            self.count_label.config(text=f"{filtered}/{total}")
    
    def update_stats_display(self, stats_data=None):
        """Обновление отображения статистики"""
        self.stats_text.config(state='normal')
        self.stats_text.delete(1.0, tk.END)
        
        # Если есть данные статистики из анализа
        if stats_data:
            stats_text = f"Статистика анализа:\n"
            stats_text += "=" * 25 + "\n"
            stats_text += f"Всего записей: {stats_data['total']}\n"
            stats_text += f"Опасных: {stats_data['danger']}\n"
            stats_text += f"Процент: {(stats_data['danger']/stats_data['total']*100 if stats_data['total'] > 0 else 0):.1f}%\n"
            
            if stats_data['danger_lines']:
                stats_text += f"\nОпасные строки:\n"
                stats_text += f"{', '.join(map(str, stats_data['danger_lines']))}\n"
            
            self.stats_text.insert(1.0, stats_text)
            self.status_var.set(f"Анализ завершен. Обработано {stats_data['total']} записей")
        else:
            # Текущая статистика
            truedangers = [lvl for lvl in self.dangers if self.dangers[lvl]]
            
            stats_text = f"Текущие настройки:\n"
            stats_text += "=" * 25 + "\n"
            stats_text += f"Опасные уровни:\n"
            
            if truedangers:
                for lvl in truedangers:
                    stats_text += f"• {lvl}\n"
            else:
                stats_text += "не заданы\n"
            
            if self.parsed_entries:
                stats_text += f"\nТекущая сессия:\n"
                stats_text += f"Записей: {len(self.parsed_entries)}\n"
                danger_count = len([e for e in self.parsed_entries if e["is_danger"]])
                stats_text += f"Опасных: {danger_count}\n"
            
            self.stats_text.insert(1.0, stats_text)
        
        self.stats_text.config(state='disabled')

def main():
    root = tk.Tk()
    app = LogAnalyzerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
