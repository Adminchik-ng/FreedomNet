import customtkinter as ctk
from tkinter import filedialog, messagebox, font
from tkinter import ttk
from tkinter.ttk import Style
import os
import random
from typing import List, Dict, Any

# Внутренние импорты модуля
from config import LANG_STRINGS, SCHEMES, SOURCES
from models import LinkItem
from processor import LinkProcessor
from network import NetworkManager


class LinkCollectorApp(ctk.CTk):
    """
    Основное GUI-приложение для сбора, фильтрации и отображения ссылок.
    Таблица занимает всё доступное вертикальное пространство,
    колонка 'link' растягивается по горизонтали.
    """
    def __init__(self):
        super().__init__()
        self.title(LANG_STRINGS["ru"]["title"])
        self.geometry("930x620")
        self.minsize(930, 620)
        self.current_lang = "ru"
        self.current_theme = "dark"
        self.set_theme_mode()

        self.links: List[LinkItem] = []
        self.filtered_links: List[LinkItem] = []

        self.last_status_key = "status_wait"
        self.last_status_args: Dict[str, Any] = {}
        self.full_status_message = self.tr('status_wait')

        # Настройка шрифтов для таблицы и заголовков
        self.table_font = font.Font(family="Roboto", size=13)
        self.header_font_family = "Roboto"
        self.header_font_size = 11

        self.processor = LinkProcessor()
        self.network_manager = NetworkManager(
            status_callback=self.update_status,
            result_callback=self.on_loading_complete
        )

        self.init_ui()
        self.update_ui_language()

        # Привязка горячих клавиш к функционалу копирования, сохранения и фильтрации
        self.bind_all("<Control-Key>", self.handle_hotkey)
        self.bind_all("<Command-Key>", self.handle_hotkey)
        self.bind("<Button-1>", self.clear_selection_on_click, add=True)
        self.bind("<FocusOut>", self.clear_table_selection)
        self.bind("<Escape>", self.clear_table_selection)

    def set_theme_mode(self):
        """Устанавливает тему интерфейса (светлая/тёмная)."""
        ctk.set_appearance_mode(self.current_theme)

    def handle_hotkey(self, event):
        ctrl_pressed = (event.state & 0x4) != 0  # проверка, что Ctrl удерживается
        if not ctrl_pressed:
            return  # без Ctrl игнорируем горячие клавиши
        
        key_actions = {
            67: self.copy_selected_links_event,  # Ctrl+C
            83: self.save_filtered_event,        # Ctrl+S
            70: self.filter_hotkey_event,        # Ctrl+F
            76: self.load_hotkey_event            # Ctrl+L
        }
        action = key_actions.get(event.keycode)
        if action:
            action(event)
            return "break"

    def filter_hotkey_event(self, event=None):
        """Запускает применение фильтра по горячей клавише."""
        self.apply_filter()
        return "break"

    def load_hotkey_event(self, event=None):
        """Запускает загрузку источников по горячей клавише."""
        self.start_loading_thread()
        return "break"

    def tr(self, key: str) -> str:
        """Получение перевода строки по ключу из текущей локализации."""
        return LANG_STRINGS.get(self.current_lang, {}).get(key, f"<{key}>")

    def setup_table_styles(self):
        """Настройка стилей для таблицы и скроллбаров ttk.Treeview."""
        is_dark = self.current_theme == "dark"

        bg_color = "#2b2b2b" if is_dark else "#ebebeb"
        fg_color = "#dce4ee" if is_dark else "#1a1a1a"
        header_bg = "#343638" if is_dark else "#dde2e9"
        header_fg = "#dce4ee" if is_dark else "#1a1a1a"
        selected_bg = "#565b5e" if is_dark else "#c2c6cb"

        self.style = Style(self)
        self.style.theme_use("default")

        self.style.configure("Treeview",
                              background=bg_color,
                              foreground=fg_color,
                              fieldbackground=bg_color,
                              borderwidth=0,
                              rowheight=30,
                              font=self.table_font
                              )
        self.style.configure("Treeview.Heading",
                              background=header_bg,
                              foreground=header_fg,
                              borderwidth=1,
                              relief="flat",
                              font=(self.header_font_family, self.header_font_size, "bold"),
                              padding=(10, 8)
                              )
        self.style.map("Treeview.Heading",
                        background=[('active', selected_bg)]
                        )
        self.style.map('Treeview',
                        background=[('selected', selected_bg)],
                        foreground=[('selected', fg_color)]
                        )
        self.style.configure("Vertical.TScrollbar",
                              background=header_bg,
                              troughcolor=bg_color,
                              bordercolor=bg_color,
                              arrowcolor=fg_color)
        self.style.map("Vertical.TScrollbar",
                        background=[('active', selected_bg), ('pressed', selected_bg)])
        self.style.configure("Horizontal.TScrollbar",
                              background=header_bg,
                              troughcolor=bg_color,
                              bordercolor=bg_color,
                              arrowcolor=fg_color)
        self.style.map("Horizontal.TScrollbar",
                        background=[('active', selected_bg), ('pressed', selected_bg)])

        if hasattr(self, 'table'):
            self.table.configure(style="Treeview")
            self.scrollbar.configure(style="Vertical.TScrollbar")
            self.x_scrollbar.configure(style="Horizontal.TScrollbar")

    def init_ui(self):
        """Инициализация интерфейса, создание и расположение виджетов."""
        self.grid_columnconfigure(0, weight=1)
        # Гарантирует, что строка с таблицей растянется по вертикали
        self.grid_rowconfigure(2, weight=1)

        # Верхняя панель с кнопками действия
        self.action_frame = ctk.CTkFrame(self)
        self.action_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.load_button = ctk.CTkButton(self.action_frame, width=150, command=self.start_loading_thread)
        self.load_button.pack(side="left", padx=5)
        self.filter_button = ctk.CTkButton(self.action_frame, width=120, command=self.apply_filter)
        self.filter_button.pack(side="left", padx=5)
        self.copy_button = ctk.CTkButton(self.action_frame, width=120, command=self.copy_selected_links)
        self.copy_button.pack(side="left", padx=5)
        self.save_button = ctk.CTkButton(self.action_frame, width=120, command=self.save_filtered)
        self.save_button.pack(side="left", padx=5)

        # Панель фильтров с комбобоксами и полями ввода
        self.filter_frame = ctk.CTkFrame(self)
        self.filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.filter_frame.grid_columnconfigure((0, 1, 6), weight=0)
        self.filter_frame.grid_columnconfigure((2, 4), weight=1)
        self.filter_frame.grid_columnconfigure((3, 5), weight=2)

        self.scheme_combo = ctk.CTkComboBox(self.filter_frame, width=120,
                                             values=[self.tr('scheme_all')] + SCHEMES,
                                             state="readonly")
        self.scheme_combo.grid(row=0, column=0, padx=(5, 2), pady=5, sticky="ew")

        self.type_combo = ctk.CTkComboBox(self.filter_frame, width=100,
                                          values=[self.tr('type_all')] + list(SOURCES.keys()),
                                          state="readonly")
        self.type_combo.grid(row=0, column=1, padx=2, pady=5, sticky="ew")

        self.port_entry = ctk.CTkEntry(self.filter_frame, width=115, placeholder_text=self.tr('port_placeholder'))
        self.port_entry.grid(row=0, column=2, padx=2, pady=5, sticky="ew")
        self.port_entry.insert(0, "443")

        self.sni_entry = ctk.CTkEntry(self.filter_frame, placeholder_text=self.tr('sni_placeholder'))
        self.sni_entry.grid(row=0, column=3, padx=2, pady=5, sticky="ew")

        self.ip_entry = ctk.CTkEntry(self.filter_frame, width=95, placeholder_text=self.tr('ip_placeholder'))
        self.ip_entry.grid(row=0, column=4, padx=2, pady=5, sticky="ew")

        self.generic_entry = ctk.CTkEntry(self.filter_frame, placeholder_text=self.tr('generic_placeholder'))
        self.generic_entry.grid(row=0, column=5, padx=2, pady=5, sticky="ew")

        self.max_entry = ctk.CTkEntry(self.filter_frame, width=90, placeholder_text=self.tr('max_placeholder'))
        self.max_entry.grid(row=0, column=6, padx=(2, 5), pady=5, sticky="e")

        # Основная таблица с прокрутками
        main_table_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        main_table_frame.grid_columnconfigure(0, weight=1)
        main_table_frame.grid_rowconfigure(0, weight=1)

        table_container = ctk.CTkFrame(main_table_frame, fg_color="transparent")
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        self.scrollbar = ttk.Scrollbar(table_container, orient="vertical")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.x_scrollbar = ttk.Scrollbar(table_container, orient="horizontal")
        self.x_scrollbar.grid(row=1, column=0, sticky="ew")

        self.table = ttk.Treeview(
            table_container,
            columns=("index", "link"),
            show="headings",
            yscrollcommand=self.scrollbar.set,
            xscrollcommand=self.x_scrollbar.set,
            selectmode="extended"
        )
        self.scrollbar.config(command=self.table.yview)
        self.x_scrollbar.config(command=self.table.xview)

        self.table.column("index", width=80, minwidth=50, stretch=False, anchor="w")
        self.table.column("link", width=600, minwidth=200, stretch=True, anchor="w")

        self.table.heading("index", text="", anchor="w")
        self.table.heading("link", text="", anchor="w")

        self.table.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=0)

        self.setup_table_styles()

        # Нижняя панель с переключателями языка и темы, а также статусом
        self.bottom_frame = ctk.CTkFrame(self, height=40)
        self.bottom_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.bottom_frame.bind("<Configure>", self._on_bottom_frame_resize)

        self.lang_button = ctk.CTkButton(self.bottom_frame, width=40, text=self.current_lang.upper(),
                                         command=self.toggle_language)
        self.lang_button.pack(side="left", padx=(5, 10))

        self.theme_label = ctk.CTkLabel(self.bottom_frame, text="...")
        self.theme_label.pack(side="left", padx=(0, 5))

        self.theme_switch = ctk.CTkSwitch(self.bottom_frame, text="",
                                          command=self.toggle_theme, onvalue="light", offvalue="dark")
        self.theme_switch.pack(side="left", padx=(0, 20))

        self.status_label = ctk.CTkLabel(self.bottom_frame, text=self.tr('status_wait'), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=5)

    def show_notification(self, title: str, message: str, duration: int = 3000):
        """
        Показывает всплывающее уведомление с полупрозрачным эффектом и автозакрытием.

        :param title: Заголовок окна уведомления
        :param message: Текст сообщения
        :param duration: Время отображения в мс, затем происходит плавное исчезновение
        """
        toplevel = ctk.CTkToplevel(self)
        toplevel.title(title)
        toplevel.overrideredirect(True)

        window_width, window_height = 300, 80
        self.update_idletasks()
        main_x_root = self.winfo_rootx()
        main_y_root = self.winfo_rooty()
        main_width = self.winfo_width()
        main_height = self.winfo_height()

        x = int(main_x_root + (main_width / 2) - (window_width / 2))
        y = int(main_y_root + (main_height / 2) - (window_height / 2))
        toplevel.geometry(f"{window_width}x{window_height}+{x}+{y}")

        frame = ctk.CTkFrame(toplevel)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        noti_font = ctk.CTkFont(family="Roboto", size=15, weight="bold")
        title_label = ctk.CTkLabel(frame, text=title, font=noti_font, anchor="w")
        title_label.pack(fill="x", padx=10, pady=(5, 0))
        message_label = ctk.CTkLabel(frame, text=message, wraplength=window_width - 20, anchor="w")
        message_label.pack(fill="x", padx=10, pady=(0, 5))

        toplevel.transient(self)
        toplevel.lift()
        toplevel.attributes("-alpha", 0.95)

        fade_time = 500
        steps = 10
        delay = fade_time // steps

        def fade_out(step):
            if not toplevel.winfo_exists():
                return
            if step > 0:
                alpha = 0.95 * (step / steps)
                toplevel.attributes("-alpha", alpha)
                self.after(delay, fade_out, step - 1)
            else:
                toplevel.destroy()

        toplevel.after(duration - fade_time, fade_out, steps)
        toplevel.update()

    def clear_table_selection(self, event=None):
        """Снимает текущее выделение в таблице."""
        self.table.selection_remove(self.table.selection())

    def clear_selection_on_click(self, event):
        """
        При клике вне таблицы или её скроллбаров снимает выделение ссылок.
        Игнорирует клики по элементам таблицы и скроллбаров.
        """
        widget_clicked = event.widget
        current = widget_clicked
        while current and current != self:
            if (current == self.table or
                        current == self.scrollbar or
                        current == self.x_scrollbar):
                return
            if "TScrollbar" in current.winfo_class():
                return
            current = current.master
        self.clear_table_selection()

    def copy_selected_links_event(self, event):
        """Обработчик горячей клавиши копирования ссылок."""
        self.copy_selected_links()
        return "break"

    def copy_selected_links(self):
        """
        Копирует выделенные ссылки в буфер обмена.
        Если ничего не выделено, копирует все отфильтрованные ссылки и информирует об этом.
        """
        selected_iids = self.table.selection()
        if not selected_iids:
            if self.filtered_links:
                all_text = "\n".join([l.link.strip().replace('\n', '').replace('\r', '')
                                     for l in self.filtered_links])
                count = len(self.filtered_links)
                info_msg = self.tr('copy_all_info_msg').format(count=count)
            else:
                self.show_notification(self.tr('copy_info_title'), self.tr('copy_empty_warn'), duration=4000)
                return
        else:
            selected_links = [
                self.table.item(iid, 'values')[1].strip().replace('\n', '').replace('\r', '')
                for iid in selected_iids
            ]
            all_text = "\n".join(selected_links)
            count = len(selected_links)
            info_msg = self.tr('copy_selected_info_msg').format(count=count)

        self.clipboard_clear()
        self.clipboard_append(all_text)
        self.show_notification(self.tr('copy_info_title'), info_msg)

    def save_filtered_event(self, event):
        """Обработчик горячей клавиши сохранения ссылок."""
        self.save_filtered()
        return "break"

    def save_filtered(self):
        """
        Сохраняет выделенные или все отфильтрованные ссылки в текстовый файл,
        выбранный пользователем через диалог сохранения.
        """
        selected_iids = self.table.selection()
        links_to_save: List[str] = []
        count = 0
        is_selected_save = bool(selected_iids)

        if is_selected_save:
            links_to_save = [
                self.table.item(iid, 'values')[1].strip().replace('\n', '').replace('\r', '')
                for iid in selected_iids
            ]
            count = len(links_to_save)
            save_type_key = 'save_selected_info_msg'
        else:
            if not self.filtered_links:
                self.show_notification(self.tr('save_warn_title'), self.tr('save_warn_msg'), duration=4000)
                return
            links_to_save = [
                item.link.strip().replace('\n', '').replace('\r', '')
                for item in self.filtered_links
            ]
            count = len(links_to_save)
            save_type_key = 'save_all_info_msg'

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
                for link in links_to_save:
                    f.write(link + "\n")
            base_name = os.path.basename(file_path)
            info_msg = self.tr(save_type_key).format(count=count, file=base_name)
            self.show_notification(self.tr('save_info_title'), info_msg)
            if is_selected_save:
                self._set_status_state('save_info_msg', {'count': count, 'file': base_name})
            else:
                self._set_status_state(save_type_key, {'count': count, 'file': base_name})
        except Exception as e:
            messagebox.showerror("Error", f"Не удалось сохранить файл: {e}")
            self._thread_safe_status_update(f"[translate:Ошибка сохранения:] {e}", "error")

    def start_loading_thread(self):
        """Запускает асинхронную загрузку ссылок и блокирует кнопку загрузки."""
        self.load_button.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        self._set_status_state('status_loading', {})
        self.links.clear()
        # Перед загрузкой растягиваем колонку "link" на всю ширину для удобства
        self.table.column("link", stretch=True, width=600)
        self.network_manager.load_links_threaded(SOURCES)

    def on_loading_complete(self, all_links: List[LinkItem]):
        """Обратный вызов по завершении загрузки ссылок."""
        self.after(0, self._thread_safe_loading_complete, all_links)

    def _thread_safe_loading_complete(self, all_links: List[LinkItem]):
        """Обновляет состояние после окончания загрузки ссылок."""
        self.links = all_links
        self._set_status_state('status_done', {'count': len(self.links)})
        self.load_button.configure(state="normal")
        self.apply_filter()

    def show_links(self, links_to_show: List[LinkItem]):
        """
        Отображает ссылки в таблице, адаптируя ширину колонки "link" по максимальной длине.
        Ограничение количества выводимых ссылок задаётся в поле max_entry.
        """
        self.table.delete(*self.table.get_children())

        unique_links = list({l.link: l for l in links_to_show}.values())
        max_count_str = self.max_entry.get().strip()
        if max_count_str.isdigit():
            max_count = int(max_count_str)
            if len(unique_links) > max_count:
                unique_links = random.sample(unique_links, max_count)

        max_width = 600
        for item in unique_links:
            try:
                text_width = self.table_font.measure(item.link)
                if text_width > max_width:
                    max_width = text_width
            except Exception:
                pass

        # Фиксируем ширину колонки под максимальный размер для включения горизонтальной прокрутки
        self.table.column("link", width=max_width + 20, stretch=False)
        # Обновляем заголовок с сохранением выравнивания
        self.table.heading("link", text=self.tr('table_link'), anchor="w")

        for i, item in enumerate(unique_links, start=1):
            self.table.insert("", "end", iid=item.link, values=(i, item.link))

        self.filtered_links = unique_links

    def apply_filter(self):
        """Применяет выбранные фильтры к списку ссылок и обновляет таблицу."""
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
            full_error_message = f"{self.tr('regex_error')}: {error}"
            self._thread_safe_status_update(full_error_message, "error")
            self.table.delete(*self.table.get_children())
            self.filtered_links = []
        else:
            self.show_links(filtered_list)
            self._set_status_state('status_filtered', {'count': len(self.filtered_links)})

    def _set_status_state(self, key: str, args: Dict[str, Any]):
        """Обновляет статус бар с текстом из локализации и аргументами."""
        self.last_status_key = key
        self.last_status_args = args
        try:
            self.full_status_message = self.tr(key).format(**args)
        except Exception:
            self.full_status_message = self.tr(key)
        self.status_label.configure(text=self.full_status_message)
        self.after(10, self._truncate_status_text)

    def _truncate_status_text(self, event=None):
        """Обрезает текст статуса по ширине панели, добавляя '...' при необходимости."""
        if not self.full_status_message:
            return
        frame_width = self.bottom_frame.winfo_width()
        fixed_width_approx = 250
        available_width = max(10, frame_width - fixed_width_approx)
        max_chars = int(available_width / 8.5)
        if len(self.full_status_message) > max_chars and max_chars > 5:
            truncated_message = self.full_status_message[:max_chars - 3] + "..."
            self.status_label.configure(text=truncated_message)
        else:
            self.status_label.configure(text=self.full_status_message)

    def _on_bottom_frame_resize(self, event):
        """Обрабатывает событие изменения размера панели статуса для обновления текста."""
        self.after(10, self._truncate_status_text)

    def update_status(self, message: str, level: str):
        """Обновляет статус приложения по сообщениям из NetworkManager."""
        key_to_translate = ""
        args: Dict[str, Any] = {}

        if message.startswith("Loading: "):
            key_to_translate = "status_loading_url"
            args = {"url": message[9:]}
        elif message.startswith("Loaded: "):
            key_to_translate = "status_loaded_source"
            args = {"source": message[8:]}
        elif message.startswith("Error: "):
            key_to_translate = "status_error_source"
            args = {"error": message[7:]}
        else:
            self.after(0, self._thread_safe_status_update, message, level)
            return

        if key_to_translate:
            self.after(0, self._set_status_state, key_to_translate, args)

    def _thread_safe_status_update(self, message: str, level: str):
        """Обновляет статус в UI, безопасно вызывая из потоков."""
        self.full_status_message = message
        self.status_label.configure(text=message)
        self.after(10, self._truncate_status_text)

    def toggle_language(self):
        """Переключает язык интерфейса и обновляет UI."""
        self.current_lang = "en" if self.current_lang == "ru" else "ru"
        self.update_ui_language()

    def update_ui_language(self):
        """Обновляет тексты и подсказки всех виджетов в соответствии с текущим языком."""
        current_scheme_val = self.scheme_combo.get()
        current_type_val = self.type_combo.get()

        self.title(self.tr('title'))
        self.load_button.configure(text=self.tr('load'))
        self.filter_button.configure(text=self.tr('filter_btn'))
        self.copy_button.configure(text=self.tr('copy_btn'))
        self.save_button.configure(text=self.tr('save_btn'))

        all_schemes = self.tr('scheme_all')
        all_types = self.tr('type_all')

        self.scheme_combo.configure(values=[all_schemes] + SCHEMES)
        scheme_set_val = current_scheme_val if current_scheme_val in SCHEMES else all_schemes
        self.scheme_combo.set(scheme_set_val if scheme_set_val in self.scheme_combo.cget('values') else all_schemes)

        self.type_combo.configure(values=[all_types] + list(SOURCES.keys()))
        type_set_val = current_type_val if current_type_val in SOURCES.keys() else all_types
        self.type_combo.set(type_set_val if type_set_val in self.type_combo.cget('values') else all_types)

        self.port_entry.configure(placeholder_text=self.tr('port_placeholder'))
        self.sni_entry.configure(placeholder_text=self.tr('sni_placeholder'))
        self.ip_entry.configure(placeholder_text=self.tr('ip_placeholder'))
        self.generic_entry.configure(placeholder_text=self.tr('generic_placeholder'))
        self.max_entry.configure(placeholder_text=self.tr('max_placeholder'))

        self.table.heading("index", text=self.tr('table_index'), anchor="w")
        self.table.heading("link", text=self.tr('table_link'), anchor="w")

        self.lang_button.configure(text=self.current_lang.upper())
        self.theme_label.configure(text=self.tr('theme_label'))

        if self.last_status_key == 'regex_error':
            if self.links:
                self.apply_filter()
            else:
                self._set_status_state('status_wait', {})
        else:
            self._set_status_state(self.last_status_key, self.last_status_args)

    def toggle_theme(self):
        """Переключает тему интерфейса и обновляет стили."""
        self.current_theme = self.theme_switch.get()
        self.set_theme_mode()
        self.setup_table_styles()