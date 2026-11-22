import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, items: list[tuple[str, str]], on_select):
        super().__init__(master, width=190, corner_radius=0)
        self.grid_propagate(False)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        ctk.CTkLabel(self, text="Video Toolkit", font=ctk.CTkFont(size=18, weight="bold")).pack(padx=20, pady=(24, 20), anchor="w")
        for key, label in items:
            btn = ctk.CTkButton(self, text=label, anchor="w", height=38, fg_color="transparent",
                                text_color=("gray10", "gray90"), hover_color=("gray75", "gray30"),
                                command=lambda k=key: on_select(k))
            btn.pack(fill="x", padx=12, pady=3)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.configure(fg_color=("gray75", "gray25") if k == key else "transparent")
