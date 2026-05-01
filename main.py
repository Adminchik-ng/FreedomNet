import customtkinter as ctk
from gui import LinkCollectorApp

if __name__ == "__main__":
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    ctk.set_default_color_theme("blue")
    
    app = LinkCollectorApp()
    app.mainloop()