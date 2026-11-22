"""yt-dlp wrapper: fetch video info and download using the bundled ffmpeg."""
from __future__ import annotations

import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.core.ffmpeg_locator import get_ffmpeg_dir
from app.core.presets import DownloadSettings, build_format_selector, build_format_sort


class DownloadCancelled(Exception):
    pass


class DownloadFailed(Exception):
    """Error with a message that is safe to show to the user."""


@dataclass
class VideoInfo:
    url: str
    title: str
    channel: str
    duration: int | None
    thumbnail_url: str | None
    heights: list[int] = field(default_factory=list)   # available video heights, descending


@dataclass
class Progress:
    stage: str            # "downloading" | "processing"
    percent: float = 0.0  # 0..100 for the current file
    speed: float | None = None   # bytes/s
    eta: int | None = None       # seconds
    part: int = 1                # which stream (video/audio) is downloading


def parse_info(url: str, raw: dict[str, Any]) -> VideoInfo:
    heights = sorted({f["height"] for f in raw.get("formats", [])
                      if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
    return VideoInfo(url=url, title=raw.get("title") or "Untitled",
                     channel=raw.get("uploader") or raw.get("channel") or "",
                     duration=raw.get("duration"), thumbnail_url=raw.get("thumbnail"), heights=heights)


def friendly_error(exc: BaseException) -> str:
    msg = str(exc)
    low = msg.lower()
    rules = [
        (("unsupported url", "is not a valid url", "no video formats"), "That doesn't look like a valid video URL."),
        (("private video",), "This video is private."),
        (("sign in to confirm your age", "age-restricted", "age restricted"), "This video is age-restricted and can't be downloaded."),
        (("not available in your country", "geo", "blocked it in your country"), "This video isn't available in your region."),
        (("video unavailable", "is unavailable", "has been removed", "no longer available"), "This video is unavailable."),
        (("sign in to confirm you", "not a bot"), "YouTube asked for verification. Try again later."),
        (("unable to download", "urlopen error", "timed out", "network is unreachable", "getaddrinfo"), "Network error. Check your connection and try again."),
        (("ffmpeg",), "ffmpeg failed while processing the video."),
    ]
    for needles, text in rules:
        if any(n in low for n in needles):
            return text
    return "Something went wrong: " + msg.replace("ERROR: ", "").splitlines()[0][:200]


class _SilentLogger:
    """Windowed (no-console) builds have no stderr; keep yt-dlp from writing to it."""

    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _base_opts() -> dict[str, Any]:
    return {"logger": _SilentLogger(), "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            "ffmpeg_location": get_ffmpeg_dir(), "windowsfilenames": True}


def fetch_info(url: str) -> VideoInfo:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise DownloadFailed("Please paste a full URL starting with http:// or https://")
    try:
        with yt_dlp.YoutubeDL({**_base_opts(), "skip_download": True}) as ydl:
            raw = ydl.extract_info(url, download=False)
    except YtDlpDownloadError as exc:
        raise DownloadFailed(friendly_error(exc)) from exc
    if not raw:
        raise DownloadFailed("Couldn't read any video information from that URL.")
    return parse_info(url, raw)


def fetch_thumbnail(url: str, timeout: int = 15) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except Exception:  # noqa: BLE001 - thumbnail is optional
        return None


def build_ydl_opts(settings: DownloadSettings, on_progress: Callable[[Progress], None] | None = None,
                   cancel: threading.Event | None = None) -> dict[str, Any]:
    state = {"part": 0, "last": None}

    def hook(d: dict[str, Any]) -> None:
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled()
        if d.get("status") not in ("downloading", "finished") or on_progress is None:
            return
        name = d.get("filename")
        if name != state["last"]:
            state["last"] = name
            state["part"] += 1
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        pct = 100.0 if d["status"] == "finished" else (100.0 * d.get("downloaded_bytes", 0) / total if total else 0.0)
        on_progress(Progress("downloading", pct, d.get("speed"), d.get("eta"), state["part"]))

    def pp_hook(d: dict[str, Any]) -> None:
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled()
        if d.get("status") == "started" and on_progress is not None:
            on_progress(Progress("processing", 100.0))

    opts = {**_base_opts(), "outtmpl": "%(title).150B [%(id)s].%(ext)s",
            "paths": {"home": settings.out_dir},
            "format": build_format_selector(settings),
            "progress_hooks": [hook], "postprocessor_hooks": [pp_hook]}
    sort = build_format_sort(settings)
    if sort:
        opts["format_sort"] = sort
    if settings.kind == "audio":
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": settings.audio_format,
                                   "preferredquality": "192"}]
    else:
        opts["merge_output_format"] = settings.container
    return opts


def download(url: str, settings: DownloadSettings, on_progress: Callable[[Progress], None] | None = None,
             cancel: threading.Event | None = None) -> str:
    """Download and return the final file path. Raises DownloadCancelled / DownloadFailed."""
    try:
        with yt_dlp.YoutubeDL(build_ydl_opts(settings, on_progress, cancel)) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadCancelled:
        raise
    except YtDlpDownloadError as exc:
        # yt-dlp wraps exceptions raised in hooks; unwrap our cancellation.
        if isinstance(exc.exc_info and exc.exc_info[1], DownloadCancelled) or (cancel and cancel.is_set()):
            raise DownloadCancelled() from exc
        raise DownloadFailed(friendly_error(exc)) from exc
    downloads = (info or {}).get("requested_downloads") or []
    return downloads[0].get("filepath") if downloads else ""
