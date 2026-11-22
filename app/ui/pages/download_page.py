from __future__ import annotations

import io
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from app.core import downloader as dl
from app.core.presets import AUDIO_FORMATS, VIDEO_CONTAINERS, DownloadSettings
from app.core.utils import Settings, fmt_duration, fmt_eta, fmt_speed, open_folder
from app.core.worker import Worker

BEST = "Best available"


class DownloadPage(ctk.CTkFrame):
    def __init__(self, master, worker: Worker, settings: Settings):
        super().__init__(master, fg_color="transparent")
        self.worker, self.settings = worker, settings
        self.info: dl.VideoInfo | None = None
        self.task = None
        self.result_path = ""
        self._thumb_ref = None

        ctk.CTkLabel(self, text="YT Download", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=28, pady=(28, 12), anchor="w")
        self._build_input()
        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=620)
        self.status.pack(padx=28, pady=(8, 0), fill="x")
        self._build_info()
        self._build_options()
        self._build_progress()
        self._build_done()
        self._sections = [self.info_box, self.options_box, self.progress_box, self.done_box]
        self._show()

    # ---- layout ------------------------------------------------------------------------
    def _build_input(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=28, fill="x")
        self.url_entry = ctk.CTkEntry(row, placeholder_text="Paste a YouTube URL here", height=38)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda _e: self.fetch())
        self.fetch_btn = ctk.CTkButton(row, text="Fetch", width=100, height=38, command=self.fetch)
        self.fetch_btn.pack(side="left", padx=(10, 0))

    def _build_info(self) -> None:
        self.info_box = ctk.CTkFrame(self)
        self.thumb_label = ctk.CTkLabel(self.info_box, text="", width=192, height=108)
        self.thumb_label.pack(side="left", padx=14, pady=14)
        col = ctk.CTkFrame(self.info_box, fg_color="transparent")
        col.pack(side="left", fill="both", expand=True, pady=14)
        self.title_label = ctk.CTkLabel(col, text="", font=ctk.CTkFont(size=15, weight="bold"), anchor="w", justify="left", wraplength=480)
        self.title_label.pack(anchor="w", fill="x")
        self.meta_label = ctk.CTkLabel(col, text="", anchor="w", text_color=("gray30", "gray70"))
        self.meta_label.pack(anchor="w", pady=(4, 0))

    def _build_options(self) -> None:
        box = self.options_box = ctk.CTkFrame(self)
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(14, 6))
        grid.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid, text="Type").grid(row=0, column=0, sticky="w", pady=6)
        self.kind_btn = ctk.CTkSegmentedButton(grid, values=["Video", "Audio only"], command=lambda _v: self._sync_kind())
        self.kind_btn.set("Video")
        self.kind_btn.grid(row=0, column=1, sticky="w", padx=14)

        self.quality_lbl = ctk.CTkLabel(grid, text="Quality")
        self.quality_lbl.grid(row=1, column=0, sticky="w", pady=6)
        self.quality_menu = ctk.CTkOptionMenu(grid, values=[BEST], width=170)
        self.quality_menu.grid(row=1, column=1, sticky="w", padx=14)

        self.format_lbl = ctk.CTkLabel(grid, text="Format")
        self.format_lbl.grid(row=2, column=0, sticky="w", pady=6)
        self.container_menu = ctk.CTkOptionMenu(grid, values=VIDEO_CONTAINERS, width=170)
        self.audio_menu = ctk.CTkOptionMenu(grid, values=AUDIO_FORMATS, width=170)
        self.container_menu.grid(row=2, column=1, sticky="w", padx=14)
        self.audio_menu.grid(row=2, column=1, sticky="w", padx=14)

        ctk.CTkLabel(grid, text="Save to").grid(row=3, column=0, sticky="w", pady=6)
        folder = ctk.CTkFrame(grid, fg_color="transparent")
        folder.grid(row=3, column=1, sticky="ew", padx=14)
        self.folder_entry = ctk.CTkEntry(folder)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(folder, text="Browse", width=80, command=self._browse).pack(side="left", padx=(8, 0))

        self.download_btn = ctk.CTkButton(box, text="Download", height=40, command=self.start_download)
        self.download_btn.pack(padx=14, pady=(8, 14), anchor="e")

        self.container_menu.set(self.settings.get("container", "mp4"))
        self.audio_menu.set(self.settings.get("audio_format", "mp3"))
        self.folder_entry.insert(0, self.settings.get("out_dir", DownloadSettings().out_dir))
        if self.settings.get("kind") == "audio":
            self.kind_btn.set("Audio only")
        self._sync_kind()

    def _build_progress(self) -> None:
        box = self.progress_box = ctk.CTkFrame(self)
        self.progress_label = ctk.CTkLabel(box, text="", anchor="w")
        self.progress_label.pack(fill="x", padx=14, pady=(14, 6))
        self.progress_bar = ctk.CTkProgressBar(box)
        self.progress_bar.pack(fill="x", padx=14)
        self.progress_bar.set(0)
        ctk.CTkButton(box, text="Cancel", width=90, fg_color="gray40", hover_color="gray30",
                      command=self.cancel).pack(padx=14, pady=14, anchor="e")

    def _build_done(self) -> None:
        box = self.done_box = ctk.CTkFrame(self)
        self.done_label = ctk.CTkLabel(box, text="", anchor="w", justify="left", wraplength=620, font=ctk.CTkFont(size=14))
        self.done_label.pack(fill="x", padx=14, pady=(14, 8))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(padx=14, pady=(0, 14), anchor="w")
        ctk.CTkButton(row, text="Open folder", command=lambda: open_folder(self.result_path or self.folder_entry.get(), bool(self.result_path))).pack(side="left")
        ctk.CTkButton(row, text="Download another", fg_color="gray40", hover_color="gray30", command=self.reset).pack(side="left", padx=10)

    def _show(self, *sections) -> None:
        for s in self._sections:
            s.pack_forget()
        for s in sections:
            s.pack(padx=28, pady=(14, 0), fill="x")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.configure(text=text, text_color=("#c0392b", "#ff6b6b") if error else ("gray30", "gray70"))

    def _sync_kind(self) -> None:
        audio = self.kind_btn.get() == "Audio only"
        for w in (self.quality_lbl, self.quality_menu, self.container_menu):
            (w.grid_remove if audio else w.grid)()
        self.audio_menu.grid() if audio else self.audio_menu.grid_remove()

    def _browse(self) -> None:
        path = filedialog.askdirectory(initialdir=self.folder_entry.get() or None)
        if path:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)

    # ---- actions -----------------------------------------------------------------------
    def fetch(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("Paste a video URL first.", error=True)
            return
        self.fetch_btn.configure(state="disabled")
        self._show()
        self._set_status("Fetching video info...")

        def job(_task):
            info = dl.fetch_info(url)
            thumb = dl.fetch_thumbnail(info.thumbnail_url) if info.thumbnail_url else None
            return info, thumb

        self.worker.submit(job, on_result=self._on_info, on_error=self._on_fetch_error)

    def _on_fetch_error(self, exc: BaseException) -> None:
        self.fetch_btn.configure(state="normal")
        self._set_status(str(exc) if isinstance(exc, dl.DownloadFailed) else dl.friendly_error(exc), error=True)

    def _on_info(self, result) -> None:
        info, thumb = result
        self.info = info
        self.fetch_btn.configure(state="normal")
        self._set_status("")
        self.title_label.configure(text=info.title)
        self.meta_label.configure(text=" - ".join(x for x in (info.channel, fmt_duration(info.duration)) if x))
        self._thumb_ref = None
        self.thumb_label.configure(image=None, text="No preview")
        if thumb:
            try:
                img = Image.open(io.BytesIO(thumb)).convert("RGB")
                img.thumbnail((192, 108))
                self._thumb_ref = ctk.CTkImage(img, size=img.size)
                self.thumb_label.configure(image=self._thumb_ref, text="")
            except Exception:  # noqa: BLE001 - preview is optional
                pass
        heights = [f"{h}p" for h in info.heights]
        self.quality_menu.configure(values=[BEST] + heights)
        saved = self.settings.get("quality", BEST)
        self.quality_menu.set(saved if saved in heights else BEST)
        self._show(self.info_box, self.options_box)

    def _collect(self) -> DownloadSettings:
        audio = self.kind_btn.get() == "Audio only"
        q = self.quality_menu.get()
        return DownloadSettings(kind="audio" if audio else "video",
                                height=None if q == BEST else int(q[:-1]),
                                container=self.container_menu.get(), audio_format=self.audio_menu.get(),
                                out_dir=self.folder_entry.get().strip() or DownloadSettings().out_dir)

    def start_download(self) -> None:
        if not self.info:
            return
        ds = self._collect()
        self.settings.update(kind=ds.kind, quality=self.quality_menu.get(), container=ds.container,
                             audio_format=ds.audio_format, out_dir=ds.out_dir)
        self._set_status("")
        self.progress_label.configure(text="Starting...")
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self._show(self.info_box, self.progress_box)
        url = self.info.url
        self.task = self.worker.submit(lambda t: dl.download(url, ds, t.progress, t.cancelled),
                                       on_result=self._on_done, on_error=self._on_download_error,
                                       on_progress=self._on_progress)

    def _on_progress(self, p: dl.Progress) -> None:
        if p.stage == "processing":
            self.progress_label.configure(text="Processing (merging / converting)...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            return
        what = "audio" if (self.kind_btn.get() == "Audio only" or p.part > 1) else "video"
        extra = "  -  ".join(x for x in (fmt_speed(p.speed), fmt_eta(p.eta)) if x)
        self.progress_label.configure(text=f"Downloading {what}: {p.percent:.0f}%" + (f"  -  {extra}" if extra else ""))
        self.progress_bar.set(p.percent / 100)

    def _stop_progress(self) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")

    def _on_done(self, path: str) -> None:
        self._stop_progress()
        self.task = None
        self.result_path = path
        self.done_label.configure(text=f"Done! Saved to:\n{path or self.folder_entry.get()}")
        self._show(self.info_box, self.done_box)

    def _on_download_error(self, exc: BaseException) -> None:
        self._stop_progress()
        self.task = None
        if isinstance(exc, dl.DownloadCancelled):
            self._set_status("Download cancelled.")
        else:
            self._set_status(str(exc) if isinstance(exc, dl.DownloadFailed) else dl.friendly_error(exc), error=True)
        self._show(self.info_box, self.options_box)

    def cancel(self) -> None:
        if self.task:
            self.progress_label.configure(text="Cancelling...")
            self.task.cancel()

    def reset(self) -> None:
        self.info = None
        self.url_entry.delete(0, "end")
        self._set_status("")
        self._show()
