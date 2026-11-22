"""Locate the bundled ffmpeg binary (never relies on the user's PATH in shipped builds)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_EXE = ".exe" if os.name == "nt" else ""


def _bundled_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "resources" / "bin" / "windows"
    return Path(__file__).resolve().parent.parent / "resources" / "bin" / "windows"


def _find(name: str) -> str:
    exe = f"{name}{_EXE}"
    bundled = _bundled_dir() / exe
    if bundled.is_file():
        return str(bundled)
    if not getattr(sys, "frozen", False):
        # Dev-only fallback (e.g. developing on macOS): FFMPEG_DIR env var, then PATH.
        env_dir = os.environ.get("FFMPEG_DIR")
        if env_dir and (Path(env_dir) / exe).is_file():
            return str(Path(env_dir) / exe)
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        f"Bundled {exe} not found at {bundled}. Run `python scripts/fetch_ffmpeg.py`."
    )


def get_ffmpeg() -> str:
    return _find("ffmpeg")


def get_ffmpeg_dir() -> str:
    """Directory containing ffmpeg, suitable for yt-dlp's `ffmpeg_location`."""
    return str(Path(get_ffmpeg()).parent)
