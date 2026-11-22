import customtkinter as ctk

from app.core.utils import Settings
from app.core.worker import Worker
from app.ui.pages.convert_page import ConvertPage
from app.ui.pages.download_page import DownloadPage
from app.ui.sidebar import Sidebar


class AppWindow(ctk.CTk):
    def __init__(self, settings: Settings | None = None):
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.title("YT Downloader")
        self.geometry("900x620")
        self.minsize(760, 560)
        self.settings = settings or Settings()
        self.worker = Worker()
        self.worker.attach(self)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self, [("download", "YT Download"), ("convert", "Convert Video")], self.show_page)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.pages = {
            "download": DownloadPage(self, self.worker, self.settings),
            "convert": ConvertPage(self, self.worker, self.settings),
        }
        for page in self.pages.values():
            page.grid(row=0, column=1, sticky="nsew")
        self.show_page("download")

    def show_page(self, key: str) -> None:
        self.pages[key].tkraise()
        self.sidebar.set_active(key)
