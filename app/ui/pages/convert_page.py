from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from app.core import converter as cv
from app.core.presets import CONVERT_PRESETS, HW_ENCODERS, VENDOR_LABELS, ConvertPreset, pick_hw
from app.core.utils import Settings, fmt_duration, open_folder
from app.core.worker import Worker

VIDEO_TYPES = [("Video / audio files", "*.mp4 *.mkv *.webm *.mov *.avi *.flv *.wmv *.m4v *.ts *.mpg *.mpeg *.3gp *.mp3 *.m4a *.opus *.wav *.flac *.ogg"),
               ("All files", "*.*")]


AUTO_LABEL = "Auto (GPU if available)"
CPU_LABEL = "CPU (software)"


class ConvertPage(ctk.CTkFrame):
    def __init__(self, master, worker: Worker, settings: Settings):
        super().__init__(master, fg_color="transparent")
        self.worker, self.settings = worker, settings
        self.media: cv.MediaInfo | None = None
        self.task = None
        self.result_path = ""
        self._labels = {p.label: p for p in CONVERT_PRESETS.values()}
        self.working_hw: set[str] = set()
        self._hw_detected = False
        self._enc_choices = {AUTO_LABEL: "auto", CPU_LABEL: "cpu"}

        ctk.CTkLabel(self, text="Convert Video", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=28, pady=(28, 12), anchor="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=28, fill="x")
        self.file_entry = ctk.CTkEntry(row, placeholder_text="Choose a video file to convert", height=38)
        self.file_entry.pack(side="left", fill="x", expand=True)
        self.file_entry.bind("<Return>", lambda _e: self.load_file(self.file_entry.get().strip().strip('"')))
        ctk.CTkButton(row, text="Choose file", width=110, height=38, command=self.choose_file).pack(side="left", padx=(10, 0))

        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=620)
        self.status.pack(padx=28, pady=(8, 0), fill="x")

        self.info_box = ctk.CTkFrame(self)
        self.info_label = ctk.CTkLabel(self.info_box, text="", anchor="w", justify="left", wraplength=620)
        self.info_label.pack(fill="x", padx=14, pady=14)

        self._build_options()
        self._build_progress()
        self._build_done()
        self._sections = [self.info_box, self.options_box, self.progress_box, self.done_box]
        self._show()
        self.worker.submit(lambda _t: cv.detect_working_hw_encoders(), on_result=self._on_hw_detected,
                           on_error=lambda _e: self._on_hw_detected(set()))

    def _on_hw_detected(self, working: set[str]) -> None:
        self.working_hw = working
        self._hw_detected = True
        vendors = [v for v in VENDOR_LABELS if any(e.vendor == v and e.encoder in working
                                                   for lst in HW_ENCODERS.values() for e in lst)]
        for v in vendors:
            self._enc_choices[f"GPU only: {VENDOR_LABELS[v]}"] = v
        self.encoder_menu.configure(values=list(self._enc_choices))
        saved = self.settings.get("convert_encoder", AUTO_LABEL)
        self.encoder_menu.set(saved if saved in self._enc_choices else AUTO_LABEL)
        self._sync_preset()

    def _build_options(self) -> None:
        box = self.options_box = ctk.CTkFrame(self)
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(14, 6))
        grid.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grid, text="Convert to").grid(row=0, column=0, sticky="w", pady=6)
        self.preset_menu = ctk.CTkOptionMenu(grid, values=list(self._labels), width=330, command=lambda _v: self._sync_preset())
        self.preset_menu.grid(row=0, column=1, sticky="w", padx=14)

        self.quality_lbl = ctk.CTkLabel(grid, text="Quality")
        self.quality_lbl.grid(row=1, column=0, sticky="w", pady=6)
        q = ctk.CTkFrame(grid, fg_color="transparent")
        q.grid(row=1, column=1, sticky="ew", padx=14)
        self.quality_slider = ctk.CTkSlider(q, from_=16, to=35, number_of_steps=19, width=260, command=self._on_quality)
        self.quality_slider.pack(side="left")
        self.quality_value = ctk.CTkLabel(q, text="")
        self.quality_value.pack(side="left", padx=10)

        ctk.CTkLabel(grid, text="Encoder").grid(row=2, column=0, sticky="w", pady=6)
        enc = ctk.CTkFrame(grid, fg_color="transparent")
        enc.grid(row=2, column=1, sticky="ew", padx=14)
        self.encoder_menu = ctk.CTkOptionMenu(enc, values=list(self._enc_choices), width=230)
        self.encoder_menu.pack(side="left")
        self.encoder_hint = ctk.CTkLabel(enc, text="Detecting GPU encoders...", text_color=("gray30", "gray70"))
        self.encoder_hint.pack(side="left", padx=10)

        ctk.CTkLabel(grid, text="Save to").grid(row=3, column=0, sticky="w", pady=6)
        folder = ctk.CTkFrame(grid, fg_color="transparent")
        folder.grid(row=3, column=1, sticky="ew", padx=14)
        self.folder_entry = ctk.CTkEntry(folder, placeholder_text="Same folder as the original")
        self.folder_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(folder, text="Browse", width=80, command=self._browse).pack(side="left", padx=(8, 0))

        self.convert_btn = ctk.CTkButton(box, text="Convert", height=40, command=self.start)
        self.convert_btn.pack(padx=14, pady=(8, 14), anchor="e")

        saved = self.settings.get("convert_preset", "h264")
        self.preset_menu.set(CONVERT_PRESETS.get(saved, CONVERT_PRESETS["h264"]).label)
        self._sync_preset()

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
        ctk.CTkButton(row, text="Open folder", command=lambda: open_folder(self.result_path, True)).pack(side="left")
        ctk.CTkButton(row, text="Convert another", fg_color="gray40", hover_color="gray30", command=self.reset).pack(side="left", padx=10)

    # ---- helpers -----------------------------------------------------------------------
    def _show(self, *sections) -> None:
        for s in self._sections:
            s.pack_forget()
        for s in sections:
            s.pack(padx=28, pady=(14, 0), fill="x")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.configure(text=text, text_color=("#c0392b", "#ff6b6b") if error else ("gray30", "gray70"))

    @property
    def preset(self) -> ConvertPreset:
        return self._labels[self.preset_menu.get()]

    def _sync_preset(self) -> None:
        p = self.preset
        gpu = [e for e in HW_ENCODERS.get(p.key, []) if e.encoder in self.working_hw]
        if p.key not in HW_ENCODERS:
            self.encoder_menu.configure(state="disabled")
            self.encoder_hint.configure(text="This format is always encoded on the CPU")
        else:
            self.encoder_menu.configure(state="normal")
            if gpu:
                text = f"GPU available: {gpu[0].label}"
            else:
                text = "No supported GPU encoder found - using CPU" if self._hw_detected else "Detecting GPU encoders..."
            self.encoder_hint.configure(text=text)
        if p.quality_flag:
            lo, hi = p.quality_range
            self.quality_slider.configure(from_=lo, to=hi, number_of_steps=hi - lo)
            self.quality_slider.set(p.default_quality)
            self._on_quality(p.default_quality)
            self.quality_lbl.grid()
            self.quality_slider.master.grid()
        else:
            self.quality_lbl.grid_remove()
            self.quality_slider.master.grid_remove()

    def _on_quality(self, value: float) -> None:
        self.quality_value.configure(text=f"{int(round(value))}  (lower = better quality, bigger file)")

    def _browse(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)

    # ---- actions -----------------------------------------------------------------------
    def choose_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=VIDEO_TYPES, initialdir=self.settings.get("convert_dir"))
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        if not path or not Path(path).is_file():
            self._set_status("File not found. Choose an existing file.", error=True)
            return
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, path)
        self.settings.update(convert_dir=str(Path(path).parent))
        self._set_status("Reading file...")
        self._show()
        self.worker.submit(lambda _t: cv.probe(path), on_result=self._on_probe,
                           on_error=lambda e: self._set_status(str(e), error=True))

    def _on_probe(self, info: cv.MediaInfo) -> None:
        self.media = info
        self._set_status("")
        parts = [Path(info.path).name]
        v = f"{info.video_codec} {info.width}x{info.height}" if info.video_codec else "no video"
        parts.append(f"Video: {v}   Audio: {info.audio_codec or 'none'}")
        parts.append(f"Duration: {fmt_duration(info.duration)}   Size: {info.size_bytes / 1_048_576:.1f} MB")
        self.info_label.configure(text="\n".join(parts))
        self._show(self.info_box, self.options_box)

    def start(self) -> None:
        if not self.media:
            return
        p = self.preset
        if p.has_video and not self.media.video_codec:
            self._set_status("This file has no video stream; choose the audio-only option.", error=True)
            return
        choice_label = self.encoder_menu.get()
        self.settings.update(convert_preset=p.key, convert_encoder=choice_label)
        hw = pick_hw(p.key, self.working_hw, self._enc_choices.get(choice_label, "auto"))
        quality = int(round(self.quality_slider.get())) if p.quality_flag else None
        src, duration = self.media.path, self.media.duration
        out_dir = self.folder_entry.get().strip() or None
        dst = cv.unique_output_path(src, p, out_dir)
        self._set_status("")
        self.progress_label.configure(text="Starting...")
        self.progress_bar.set(0)
        self._show(self.info_box, self.progress_box)
        self.task = self.worker.submit(lambda t: cv.convert_auto(src, dst, p, quality, duration, t.progress, t.cancelled, hw),
                                       on_result=self._on_done, on_error=self._on_error, on_progress=self._on_progress)

    def _on_progress(self, pr: cv.ConvertProgress) -> None:
        self.progress_label.configure(text=f"Converting: {pr.percent:.0f}%" + (f"  -  {pr.speed}" if pr.speed else ""))
        self.progress_bar.set(pr.percent / 100)

    def _on_done(self, result: tuple[str, str]) -> None:
        path, encoder = result
        self.task = None
        self.result_path = path
        self.done_label.configure(text=f"Done! Saved to:\n{path}\nEncoder used: {encoder}")
        self._show(self.info_box, self.done_box)

    def _on_error(self, exc: BaseException) -> None:
        self.task = None
        if isinstance(exc, cv.ConvertCancelled):
            self._set_status("Conversion cancelled.")
        else:
            self._set_status(str(exc) if isinstance(exc, cv.ConvertFailed) else f"Something went wrong: {exc}", error=True)
        self._show(self.info_box, self.options_box)

    def cancel(self) -> None:
        if self.task:
            self.progress_label.configure(text="Cancelling...")
            self.task.cancel()

    def reset(self) -> None:
        self.media = None
        self.file_entry.delete(0, "end")
        self._set_status("")
        self._show()
