import customtkinter as ctk
from tkinter import filedialog, messagebox
import re
import os
import random
from typing import List, Dict, Callable, Optional, Tuple, Any

# Импорты из внутренних модулей
from config import LANG_STRINGS, SCHEMES, SOURCES 
from models import LinkItem
from processor import LinkProcessor
from network import NetworkManager

class LinkCollectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(LANG_STRINGS["ru"]["title"])
        self.geometry("930x620")
        self.minsize(930, 620)
        
        self.current_lang = "ru"
        self.current_theme = "dark"
        ctk.set_appearance_mode(self.current_theme)

        self.links: List[LinkItem] = []
        self.filtered_links: List[LinkItem] = []
        
        # Для управления статусом и обрезкой текста
        self.last_status_key = "status_wait"
        self.last_status_args: Dict[str, Any] = {}
        self.full_status_message = self.tr('status_wait')

        # Инициализация логических компонентов
        self.processor = LinkProcessor()
        self.network_manager = NetworkManager(
            status_callback=self.update_status,
            result_callback=self.on_loading_complete
        )

        self.init_ui()
        self.update_ui_language()

    def tr(self, key: str) -> str:
        """Возвращает переведенную строку по ключу."""
        return LANG_STRINGS.get(self.current_lang, {}).get(key, f"<{key}>")

    def init_ui(self):
        """Создает и размещает все виджеты с использованием grid для адаптивности."""
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # 1. Фрейм действий (Row 0)
        self.action_frame = ctk.CTkFrame(self)
        self.action_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.load_button = ctk.CTkButton(self.action_frame, width=150, command=self.start_loading_thread)
        self.load_button.pack(side="left", padx=5)

        self.filter_button = ctk.CTkButton(self.action_frame, width=120, command=self.apply_filter)
        self.filter_button.pack(side="left", padx=5)

        self.copy_button = ctk.CTkButton(self.action_frame, width=120, command=self.copy_filtered)
        self.copy_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(self.action_frame, width=120, command=self.save_filtered)
        self.save_button.pack(side="left", padx=5)

        # 2. Фрейм фильтров (Row 1)
        self.filter_frame = ctk.CTkFrame(self)
        self.filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.filter_frame.grid_columnconfigure((0, 1, 6), weight=0)
        self.filter_frame.grid_columnconfigure((2, 4), weight=1)
        self.filter_frame.grid_columnconfigure((3, 5), weight=2)

        # Combo Boxes
        self.scheme_combo = ctk.CTkComboBox(self.filter_frame, width=120, values=[self.tr('scheme_all')] + SCHEMES, state="readonly")
        self.scheme_combo.grid(row=0, column=0, padx=(5, 2), pady=5, sticky="ew")
        
        self.type_combo = ctk.CTkComboBox(self.filter_frame, width=100, values=[self.tr('type_all'), *SOURCES.keys()], state="readonly")
        self.type_combo.grid(row=0, column=1, padx=2, pady=5, sticky="ew")
        
        # Entry fields
        self.port_entry = ctk.CTkEntry(self.filter_frame, width=115)
        self.port_entry.grid(row=0, column=2, padx=2, pady=5, sticky="ew")
        self.port_entry.insert(0, "443")
        
        self.sni_entry = ctk.CTkEntry(self.filter_frame)
        self.sni_entry.grid(row=0, column=3, padx=2, pady=5, sticky="ew")
        
        self.ip_entry = ctk.CTkEntry(self.filter_frame, width=95)
        self.ip_entry.grid(row=0, column=4, padx=2, pady=5, sticky="ew")

        self.generic_entry = ctk.CTkEntry(self.filter_frame, width=115)
        self.generic_entry.grid(row=0, column=5, padx=2, pady=5, sticky="ew")
        
        self.max_entry = ctk.CTkEntry(self.filter_frame, width=90)
        self.max_entry.grid(row=0, column=6, padx=(2, 5), pady=5, sticky="e")

        # 3. Текстовое поле (Row 2)
        self.text_box = ctk.CTkTextbox(self, wrap="none")
        self.text_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self.text_box.configure(state="disabled") 

        # 4. Нижний фрейм (Статус и Настройки) (Row 3)
        self.bottom_frame = ctk.CTkFrame(self, height=40)
        self.bottom_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.bottom_frame.bind("<Configure>", self._on_bottom_frame_resize)

        self.lang_button = ctk.CTkButton(self.bottom_frame, width=40, text=self.current_lang.upper(), command=self.toggle_language)
        self.lang_button.pack(side="left", padx=(5, 10))

        self.theme_label = ctk.CTkLabel(self.bottom_frame, text="...")
        self.theme_label.pack(side="left", padx=(0, 5))
        
        self.theme_switch = ctk.CTkSwitch(self.bottom_frame, text="", command=self.toggle_theme, onvalue="light", offvalue="dark")
        self.theme_switch.pack(side="left", padx=(0, 20))

        self.status_label = ctk.CTkLabel(self.bottom_frame, text=self.tr('status_wait'), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=5)

    # ------------------- Логика статуса и обрезки -------------------

    def _set_status_state(self, key: str, args: Dict[str, Any]):
        """Устанавливает статус и сохраняет ключ/аргументы для перевода и обрезки."""
        self.last_status_key = key
        self.last_status_args = args
        try:
            self.full_status_message = self.tr(key).format(**args)
        except Exception:
            self.full_status_message = self.tr(key)
            
        self.status_label.configure(text=self.full_status_message)
        self.after(10, self._truncate_status_text)

    def _truncate_status_text(self, event=None):
        """Динамически обрезает текст статуса, добавляя троеточие, если он не помещается."""
        original_message = self.full_status_message
        if not original_message:
            return

        frame_width = self.bottom_frame.winfo_width()
        # Приблизительная фиксированная ширина других элементов (lang btn + theme switch/label + padding)
        fixed_width_approx = 250
        available_width = max(10, frame_width - fixed_width_approx)
        
        # Оценка максимального количества символов
        max_chars = int(available_width / 8.5)

        if len(original_message) > max_chars and max_chars > 5:
            truncated_message = original_message[:max_chars - 3] + "..."
            self.status_label.configure(text=truncated_message)
        else:
            self.status_label.configure(text=original_message)

    def _on_bottom_frame_resize(self, event):
        """Обработчик события изменения размера фрейма."""
        self.after(10, self._truncate_status_text)

    def update_status(self, message: str, level: str):
        """
        Коллбэк для обновления статуса. Вызывается из NetworkManager в отдельном потоке (message - на EN).
        """
        key_to_translate = ""
        args: Dict[str, Any] = {}
        
        # Логика извлечения ключа и аргументов из английского сообщения потока
        if message.startswith(LANG_STRINGS["en"]["status_loading_url"].split("{")[0]):
            key_to_translate = "status_loading_url"
            try: args["url"] = message.split(": ")[1]
            except Exception: pass
        elif message.startswith(LANG_STRINGS["en"]["status_ok"].split("{")[0]):
            key_to_translate = "status_ok"
            try: 
                parts = re.findall(r'\[.+\]\s(\d+)\s.+\s(.+)', message)
                args["count"] = int(parts[0][0])
                args["url"] = parts[0][1]
            except Exception: pass
        elif message.startswith(LANG_STRINGS["en"]["status_error"].split("{")[0]):
            key_to_translate = "status_error"
            try: 
                parts = re.findall(r'\[.+\]\s(.+):\s(.+)', message)
                args["url"] = parts[0][0]
                args["error"] = parts[0][1]
            except Exception: pass
            
        final_message = message
        if key_to_translate:
             try:
               final_message = self.tr(key_to_translate).format(**args)
             except Exception:
               final_message = self.tr(key_to_translate)
        
        self.after(0, self._thread_safe_status_update, final_message, level)

    def _thread_safe_status_update(self, message: str, level: str):
        """Обновляет GUI в основном потоке."""
        self.full_status_message = message
        self.status_label.configure(text=message)
        self.after(10, self._truncate_status_text)

        if level in ("ok", "error"):
            # Временно включаем для записи статуса/ошибки
            self.text_box.configure(state="normal")
            self.text_box.insert("end", f"{message}\n")
            self.text_box.configure(state="disabled")

    # ------------------- Методы GUI -------------------

    def start_loading_thread(self):
        """Запускает процесс загрузки."""
        self.load_button.configure(state="disabled")
        
        self.text_box.configure(state="normal") 
        self.text_box.delete("1.0", "end")
        self.text_box.configure(state="disabled")
        
        self._set_status_state('status_loading', {})
        self.links.clear()
        
        self.network_manager.load_links_threaded(SOURCES)

    def on_loading_complete(self, all_links: List[LinkItem]):
        """Коллбэк, вызываемый по завершении загрузки. Обновляет GUI в основном потоке."""
        self.after(0, self._thread_safe_loading_complete, all_links)

    def _thread_safe_loading_complete(self, all_links: List[LinkItem]):
        """Обновляет GUI в основном потоке."""
        self.links = all_links
        self._set_status_state('status_done', {'count': len(self.links)})
        self.load_button.configure(state="normal")
        self.apply_filter()

    def show_links(self, links_to_show: List[LinkItem]):
        """Отображает отфильтрованный список ссылок в текстовом поле."""
        
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")

        # Убираем дубли по ссылке
        unique_links = list({l.link: l for l in links_to_show}.values())

        # Ограничение количества выводимых ссылок
        max_count_str = self.max_entry.get().strip()
        if max_count_str.isdigit():
            max_count = int(max_count_str)
            if len(unique_links) > max_count:
                # Случайные ссылки, если больше max
                unique_links = random.sample(unique_links, max_count)

        for i, item in enumerate(unique_links, start=1):
            self.text_box.insert("end", f"{i}\t{item.link}\n")

        self.text_box.configure(state="disabled")
        self.filtered_links = unique_links

    def apply_filter(self):
        """Собирает фильтры из GUI и применяет их."""
        
        if not self.links:
            self._set_status_state('status_wait', {})
            return

        filters = {
            "scheme": self.scheme_combo.get(),
            "type": self.type_combo.get(),
            "port": self.port_entry.get().strip(),
            "sni_value": self.sni_entry.get().strip(),
            "ip": self.ip_entry.get().strip(),
            "generic_search": self.generic_entry.get().strip(),
            "all_schemes_str": self.tr('scheme_all'),
            "all_types_str": self.tr('type_all'),
        }

        filtered_list, error = self.processor.filter_links(self.links, filters)

        if error:
            error_message_prefix = self.tr('regex_error')
            full_error_message = f"{error_message_prefix}: {error}"

            self.full_status_message = full_error_message
            self.status_label.configure(text=full_error_message)
            self.after(10, self._truncate_status_text)
            
            self.text_box.configure(state="normal")
            self.text_box.delete("1.0", "end")
            self.text_box.insert("end", f"{full_error_message}\n")
            self.text_box.configure(state="disabled")
            
            self.filtered_links = []
        else:
            self.show_links(filtered_list)
            self._set_status_state('status_filtered', {'count': len(self.filtered_links)})

    def copy_filtered(self):
        """Копирует отображенные ссылки в буфер обмена."""
        if not self.filtered_links:
            return
        all_text = "\n".join([l.link for l in self.filtered_links])
        self.clipboard_clear()
        self.clipboard_append(all_text)
        messagebox.showinfo(self.tr('copy_info_title'), self.tr('copy_info_msg').format(count=len(self.filtered_links)))

    def save_filtered(self):
        """Сохраняет отображенные ссылки в файл."""
        if not self.filtered_links:
            messagebox.showwarning(self.tr('save_warn_title'), self.tr('save_warn_msg'))
            return

        file_path = filedialog.asksaveasfilename(
            title=self.tr('save_dialog_title'),
            initialfile=self.tr('save_dialog_file'),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for item in self.filtered_links:
                    f.write(item.link + "\n")
            
            base_name = os.path.basename(file_path)
            messagebox.showinfo(self.tr('save_info_title'), self.tr('save_info_msg').format(count=len(self.filtered_links), file=base_name))
            self._set_status_state('save_info_msg', {'count': len(self.filtered_links), 'file': base_name})
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

    # --- Язык и Тема ---

    def toggle_language(self):
        """Переключает язык интерфейса."""
        self.current_lang = "en" if self.current_lang == "ru" else "ru"
        self.update_ui_language()

    def update_ui_language(self):
        """Обновляет текст всех виджетов в соответствии с self.current_lang."""
        
        current_scheme_val = self.scheme_combo.get()
        current_type_val = self.type_combo.get()
        
        self.title(self.tr('title'))
        
        # Фрейм действий
        self.load_button.configure(text=self.tr('load'))
        self.filter_button.configure(text=self.tr('filter_btn'))
        self.copy_button.configure(text=self.tr('copy_btn'))
        self.save_button.configure(text=self.tr('save_btn'))

        # Фрейм фильтров
        all_schemes = self.tr('scheme_all')
        all_types = self.tr('type_all')

        # Обновляем значения ComboBox
        self.scheme_combo.configure(values=[all_schemes] + SCHEMES)
        self.scheme_combo.set(current_scheme_val if current_scheme_val in SCHEMES else all_schemes)
        
        self.type_combo.configure(values=[all_types] + list(SOURCES.keys()))
        self.type_combo.set(current_type_val if current_type_val in SOURCES.keys() else all_types)
        
        # Обновление Placeholder'ов
        self.port_entry.configure(placeholder_text=self.tr('port_placeholder'))
        self.sni_entry.configure(placeholder_text=self.tr('sni_placeholder'))
        self.ip_entry.configure(placeholder_text=self.tr('ip_placeholder'))
        self.generic_entry.configure(placeholder_text=self.tr('generic_placeholder'))
        self.max_entry.configure(placeholder_text=self.tr('max_placeholder'))

        # Нижний фрейм
        self.lang_button.configure(text=self.current_lang.upper())
        self.theme_label.configure(text=self.tr('theme_label'))
        
        # Обновляем статус
        if self.last_status_key == 'regex_error':
            if self.links:
                self.apply_filter()
            else:
                 self._set_status_state('status_wait', {})
        else:
            self._set_status_state(self.last_status_key, self.last_status_args)

    def toggle_theme(self):
        """Переключает тему оформления."""
        self.current_theme = self.theme_switch.get()
        ctk.set_appearance_mode(self.current_theme)