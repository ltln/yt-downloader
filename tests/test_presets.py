from app.core.presets import (CONVERT_PRESETS, DownloadSettings, build_convert_args,
                              build_format_selector, build_format_sort)


def test_selector_best():
    assert build_format_selector(DownloadSettings()) == "bv*+ba/b"


def test_selector_height_has_fallback():
    s = build_format_selector(DownloadSettings(height=720))
    assert s.startswith("bv*[height<=720]+ba/b[height<=720]") and s.endswith("/bv*+ba/b")


def test_selector_audio():
    assert build_format_selector(DownloadSettings(kind="audio")) == "ba/b"


def test_sort_by_container():
    assert build_format_sort(DownloadSettings(container="mp4")) == ["res", "vcodec:h264", "ext:mp4:m4a"]
    assert build_format_sort(DownloadSettings(container="mkv")) == []
    assert build_format_sort(DownloadSettings(kind="audio")) == []


def test_convert_h264_args():
    args = build_convert_args(CONVERT_PRESETS["h264"], "in.mkv", "out.mp4", quality=20)
    assert args[:5] == ["-hide_banner", "-nostdin", "-y", "-i", "in.mkv"]
    assert "libx264" in args and args[args.index("-crf") + 1] == "20"
    assert args[-1] == "out.mp4" and "pipe:1" in args


def test_convert_audio_has_no_video():
    args = build_convert_args(CONVERT_PRESETS["mp3"], "in.mp4", "out.mp3")
    assert "-vn" in args and "-crf" not in args
