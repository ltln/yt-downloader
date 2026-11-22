"""Presets and option builders for downloads and conversions (pure functions, easy to test)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VIDEO_CONTAINERS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "m4a", "opus"]


@dataclass
class DownloadSettings:
    kind: str = "video"              # "video" | "audio"
    height: int | None = None         # max video height; None = best available
    container: str = "mp4"            # video container
    audio_format: str = "mp3"         # audio-only target
    out_dir: str = field(default_factory=lambda: str(Path.home() / "Downloads"))


def build_format_selector(settings: DownloadSettings) -> str:
    if settings.kind == "audio":
        return "ba/b"
    if settings.height:
        h = settings.height
        return f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b"
    return "bv*+ba/b"


def build_format_sort(settings: DownloadSettings) -> list[str]:
    """Prefer streams that mux cleanly into the chosen container."""
    if settings.kind == "audio":
        return []
    if settings.container == "mp4":
        return ["res", "vcodec:h264", "ext:mp4:m4a"]   # most compatible within chosen resolution
    if settings.container == "webm":
        return ["ext:webm"]
    return []


# --- Conversion presets -------------------------------------------------------------------

@dataclass(frozen=True)
class ConvertPreset:
    key: str
    label: str
    ext: str
    suffix: str
    video_args: tuple[str, ...]
    audio_args: tuple[str, ...]
    has_video: bool = True
    quality_flag: str | None = "-crf"   # flag that takes the quality value
    default_quality: int = 23
    quality_range: tuple[int, int] = (16, 35)


CONVERT_PRESETS: dict[str, ConvertPreset] = {
    p.key: p
    for p in [
        ConvertPreset("h264", "H.264 / AAC (MP4) - most compatible", "mp4", "h264",
                      ("-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"),
                      ("-c:a", "aac", "-b:a", "192k")),
        ConvertPreset("h265", "H.265 / AAC (MP4) - smaller files", "mp4", "h265",
                      ("-c:v", "libx265", "-preset", "medium", "-pix_fmt", "yuv420p", "-tag:v", "hvc1"),
                      ("-c:a", "aac", "-b:a", "192k"), default_quality=28, quality_range=(18, 38)),
        ConvertPreset("vp9", "VP9 / Opus (WebM)", "webm", "vp9",
                      ("-c:v", "libvpx-vp9", "-b:v", "0", "-row-mt", "1"),
                      ("-c:a", "libopus", "-b:a", "160k"), default_quality=32, quality_range=(20, 45)),
        ConvertPreset("av1", "AV1 / Opus (MKV)", "mkv", "av1",
                      ("-c:v", "libsvtav1", "-preset", "8"),
                      ("-c:a", "libopus", "-b:a", "160k"), default_quality=35, quality_range=(20, 50)),
        ConvertPreset("mp3", "Audio only - MP3", "mp3", "audio",
                      (), ("-c:a", "libmp3lame", "-q:a", "2"), has_video=False, quality_flag=None),
    ]
}


def build_convert_args(preset: ConvertPreset, src: str, dst: str, quality: int | None = None) -> list[str]:
    """ffmpeg arguments (without the ffmpeg binary itself)."""
    args = ["-hide_banner", "-nostdin", "-y", "-i", src]
    if preset.has_video:
        args += ["-map", "0:v:0", "-map", "0:a?"]
        args += list(preset.video_args)
        if preset.quality_flag:
            q = preset.default_quality if quality is None else quality
            args += [preset.quality_flag, str(q)]
    else:
        args += ["-vn"]
    args += list(preset.audio_args)
    args += ["-progress", "pipe:1", "-nostats", dst]
    return args
