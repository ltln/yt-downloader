import customtkinter as ctk


class ConvertPage(ctk.CTkFrame):
    def __init__(self, master, worker, settings):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Convert Video", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=28, pady=(28, 8), anchor="w")
        ctk.CTkLabel(self, text="Coming soon.").pack(padx=28, anchor="w")
