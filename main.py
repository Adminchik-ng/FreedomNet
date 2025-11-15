import customtkinter as ctk
# Импортируем только App, все остальные зависимости подтянутся внутри модулей
from gui import LinkCollectorApp

if __name__ == "__main__":
    # Устанавливаем масштаб по умолчанию для лучшего отображения
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    ctk.set_default_color_theme("blue")
    
    app = LinkCollectorApp()
    app.mainloop()