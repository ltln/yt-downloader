"""ffmpeg-based video conversion: probe, progress parsing, and the conversion job."""
from __future__ import annotations

import collections
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.ffmpeg_locator import get_ffmpeg
from app.core.presets import (ALL_HW_ENCODER_NAMES, ConvertPreset, HwEncoder, build_convert_args)

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ConvertCancelled(Exception):
    pass


class ConvertFailed(Exception):
    """Error with a message that is safe to show to the user."""


@dataclass
class MediaInfo:
    path: str
    duration: float | None = None
    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    audio_codec: str | None = None
    size_bytes: int = 0


@dataclass
class ConvertProgress:
    percent: float
    speed: str | None = None   # e.g. "1.8x"


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO = re.compile(r"Stream #\S+.*?Video:\s*([\w-]+)")
_SIZE = re.compile(r",\s*(\d{2,5})x(\d{2,5})")
_AUDIO = re.compile(r"Stream #\S+.*?Audio:\s*([\w-]+)")


def parse_probe_output(path: str, text: str, size_bytes: int = 0) -> MediaInfo:
    """Parse the stderr of `ffmpeg -i <file>` (avoids shipping ffprobe)."""
    info = MediaInfo(path=path, size_bytes=size_bytes)
    if m := _DURATION.search(text):
        info.duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in text.splitlines():
        if "Video:" in line and info.video_codec is None and "attached pic" not in line:
            if m := _VIDEO.search(line):
                info.video_codec = m[1]
                if s := _SIZE.search(line.split("Video:", 1)[1]):
                    info.width, info.height = int(s[1]), int(s[2])
        elif "Audio:" in line and info.audio_codec is None:
            if m := _AUDIO.search(line):
                info.audio_codec = m[1]
    return info


def probe(path: str) -> MediaInfo:
    try:
        proc = subprocess.run([get_ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", creationflags=_NO_WINDOW, timeout=60)
    except FileNotFoundError as exc:
        raise ConvertFailed(str(exc)) from exc
    info = parse_probe_output(path, proc.stderr, Path(path).stat().st_size if Path(path).exists() else 0)
    if info.video_codec is None and info.audio_codec is None:
        raise ConvertFailed("That file doesn't look like a video or audio file.")
    return info


def parse_progress_line(line: str, duration: float | None) -> float | None:
    """Return percent (0-100) for an `out_time_us=`/`out_time_ms=` line, else None."""
    key, _, value = line.strip().partition("=")
    if key not in ("out_time_us", "out_time_ms") or not duration:
        return None
    try:
        micro = int(value)          # ffmpeg reports microseconds under both keys
    except ValueError:
        return None
    return max(0.0, min(100.0, micro / 1_000_000 / duration * 100))


def unique_output_path(src: str, preset: ConvertPreset, out_dir: str | None = None) -> str:
    p = Path(src)
    folder = Path(out_dir) if out_dir else p.parent
    base = f"{p.stem}_{preset.suffix}"
    candidate = folder / f"{base}.{preset.ext}"
    n = 1
    while candidate.exists() or candidate == p:
        candidate = folder / f"{base} ({n}).{preset.ext}"
        n += 1
    return str(candidate)


def convert(src: str, dst: str, preset: ConvertPreset, quality: int | None, duration: float | None,
            on_progress: Callable[[ConvertProgress], None] | None = None,
            cancel: threading.Event | None = None, hw: HwEncoder | None = None) -> str:
    """Run ffmpeg. Returns dst. Raises ConvertCancelled / ConvertFailed."""
    cmd = [get_ffmpeg(), *build_convert_args(preset, src, dst, quality, hw)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    tail: collections.deque[str] = collections.deque(maxlen=8)
    speed = None
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if cancel is not None and cancel.is_set():
                raise ConvertCancelled()
            if line.startswith("speed="):
                speed = line.strip().split("=", 1)[1] or None
            pct = parse_progress_line(line, duration)
            if pct is not None:
                if on_progress:
                    on_progress(ConvertProgress(pct, speed))
            elif "=" not in line.split(" ", 1)[0]:
                tail.append(line.strip())
        proc.wait()
    except ConvertCancelled:
        proc.kill()
        proc.wait()
        Path(dst).unlink(missing_ok=True)
        raise
    except BaseException:
        proc.kill()
        raise
    if proc.returncode != 0:
        Path(dst).unlink(missing_ok=True)
        detail = next((t for t in reversed(tail) if t), "unknown error")
        raise ConvertFailed(f"ffmpeg failed: {detail[:200]}")
    if on_progress:
        on_progress(ConvertProgress(100.0, speed))
    return dst


def convert_auto(src: str, dst: str, preset: ConvertPreset, quality: int | None, duration: float | None,
                 on_progress: Callable[[ConvertProgress], None] | None = None,
                 cancel: threading.Event | None = None, hw: HwEncoder | None = None) -> tuple[str, str]:
    """Convert with the GPU encoder if given; on failure transparently retry on the CPU.

    Returns (dst, encoder label used).
    """
    if hw is not None:
        try:
            return convert(src, dst, preset, quality, duration, on_progress, cancel, hw), hw.label
        except ConvertFailed:
            pass  # GPU encode failed (driver, unsupported input, ...) -> software fallback below
    return convert(src, dst, preset, quality, duration, on_progress, cancel), "CPU"


def detect_working_hw_encoders(timeout: int = 20) -> set[str]:
    """Return GPU encoder names that actually work on this machine.

    The bundled ffmpeg lists every GPU encoder it was compiled with, even without that GPU, so each
    candidate is test-encoded (one tiny frame) before being offered.
    """
    try:
        ff = get_ffmpeg()
        listing = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", creationflags=_NO_WINDOW, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return set()
    working: set[str] = set()
    for name in ALL_HW_ENCODER_NAMES:
        if name not in listing:
            continue
        try:
            r = subprocess.run([ff, "-hide_banner", "-nostdin", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                                "-frames:v", "1", "-c:v", name, "-f", "null", "-"], capture_output=True,
                               creationflags=_NO_WINDOW, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            working.add(name)
    return working
