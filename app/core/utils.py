"""Small helpers: formatting, settings persistence, opening folders."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def fmt_duration(seconds: float | int | None) -> str:
    if not seconds:
        return "--:--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_speed(bps: float | None) -> str:
    if not bps:
        return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024 or unit == "GB/s":
            return f"{bps:.1f} {unit}" if unit != "B/s" else f"{bps:.0f} {unit}"
        bps /= 1024
    return ""


def fmt_eta(seconds: int | None) -> str:
    return f"ETA {fmt_duration(seconds)}" if seconds is not None else ""


# --- portable settings --------------------------------------------------------------------

def _settings_path() -> Path:
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).resolve().parent.parent.parent
    if os.access(app_dir, os.W_OK):
        return app_dir / "settings.json"          # portable: lives next to the app
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "YTDownloader"
    return base / "settings.json"


class Settings:
    """Tiny JSON key-value store. Failures to read/write are ignored (settings are optional)."""

    def __init__(self, path: Path | None = None):
        self.path = path or _settings_path()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self.data = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def update(self, **values) -> None:
        self.data.update(values)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def explorer_select_command(path: str) -> str:
    """Command line that makes Windows Explorer open the folder with `path` selected.

    Explorer needs `/select,"<path>"` with quotes around the path only, and backslashes. Passing it
    as a list to subprocess wraps the whole `/select,<path>` token in quotes when the path contains
    spaces, which Explorer can't parse (it then opens a default folder such as Documents).
    """
    return f'explorer /select,"{os.path.normpath(path).replace("/", chr(92))}"'


def open_folder(path: str, select_file: bool = False) -> None:
    """Open the folder containing `path` (or `path` itself if it is a folder), selecting the file if asked."""
    p = Path(os.path.normpath(path)) if path else Path.home()
    is_file = p.is_file()
    folder = p if p.is_dir() else p.parent
    if sys.platform == "win32":
        if select_file and is_file:
            subprocess.Popen(explorer_select_command(str(p)))   # string on purpose, see above
        else:
            os.startfile(str(folder))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)] if select_file and is_file else ["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
