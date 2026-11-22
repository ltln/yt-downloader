import shutil
import subprocess

import pytest

from app.core import converter as cv
from app.core.ffmpeg_locator import get_ffmpeg
from app.core.presets import CONVERT_PRESETS

SAMPLE = """Input #0, matroska,webm, from 'in.mkv':
  Duration: 00:01:05.50, start: 0.000000, bitrate: 187 kb/s
  Stream #0:0: Video: mjpeg (Baseline), yuvj420p(pc), 500x500, 90k tbr (attached pic)
  Stream #0:1(eng): Video: av1 (Main), yuv420p(tv, bt709), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr
  Stream #0:2(eng): Audio: opus, 48000 Hz, stereo, fltp (default)
"""


def test_parse_probe_output():
    m = cv.parse_probe_output("in.mkv", SAMPLE, 100)
    assert (m.video_codec, m.width, m.height, m.audio_codec) == ("av1", 1920, 1080, "opus")
    assert m.duration == pytest.approx(65.5)


def test_parse_probe_audio_only():
    m = cv.parse_probe_output("a.mp3", "  Duration: 00:00:10.00, x\n  Stream #0:0: Audio: mp3, 44100 Hz, stereo")
    assert m.video_codec is None and m.audio_codec == "mp3" and m.duration == 10


def test_parse_progress_line():
    assert cv.parse_progress_line("out_time_us=5000000", 10) == 50.0
    assert cv.parse_progress_line("out_time_ms=20000000", 10) == 100.0   # clamped
    assert cv.parse_progress_line("out_time_us=N/A", 10) is None
    assert cv.parse_progress_line("frame=12", 10) is None
    assert cv.parse_progress_line("out_time_us=1", None) is None


def test_unique_output_path(tmp_path):
    src = tmp_path / "clip.mkv"
    src.write_text("x")
    p = CONVERT_PRESETS["h264"]
    first = cv.unique_output_path(str(src), p)
    assert first.endswith("clip_h264.mp4")
    (tmp_path / "clip_h264.mp4").write_text("x")
    assert cv.unique_output_path(str(src), p).endswith("clip_h264 (1).mp4")


def _ffmpeg_or_skip():
    try:
        return get_ffmpeg()
    except FileNotFoundError:
        pytest.skip("ffmpeg not available")


def _make_clip(tmp_path):
    ff = _ffmpeg_or_skip()
    src = tmp_path / "in.mkv"
    subprocess.run([ff, "-hide_banner", "-y", "-f", "lavfi", "-i", "testsrc=d=1:s=160x120:r=15",
                    "-f", "lavfi", "-i", "sine=d=1", "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(src)],
                   check=True, capture_output=True)
    return src


@pytest.mark.parametrize("key,codec", [("h264", "h264"), ("vp9", "vp9")])
def test_convert_real_ffmpeg(tmp_path, key, codec):
    src = _make_clip(tmp_path)
    info = cv.probe(str(src))
    assert info.video_codec == "mpeg4" and info.duration == pytest.approx(1, abs=0.2)
    preset, seen = CONVERT_PRESETS[key], []
    dst = cv.unique_output_path(str(src), preset)
    cv.convert(str(src), dst, preset, None, info.duration, seen.append)
    assert cv.probe(dst).video_codec == codec
    assert seen and seen[-1].percent == 100.0


def test_convert_audio_only_and_cancel(tmp_path):
    import threading
    src = _make_clip(tmp_path)
    p = CONVERT_PRESETS["mp3"]
    dst = cv.unique_output_path(str(src), p)
    cv.convert(str(src), dst, p, None, 1.0)
    m = cv.probe(dst)
    assert m.video_codec is None and m.audio_codec == "mp3"
    ev = threading.Event(); ev.set()
    dst2 = str(tmp_path / "x.mp4")
    with pytest.raises(cv.ConvertCancelled):
        cv.convert(str(src), dst2, CONVERT_PRESETS["h264"], None, 1.0, cancel=ev)
    assert not (tmp_path / "x.mp4").exists()


def test_convert_failure_message(tmp_path):
    _ffmpeg_or_skip()
    bad = tmp_path / "bad.mkv"
    bad.write_text("not media")
    with pytest.raises(cv.ConvertFailed):
        cv.convert(str(bad), str(tmp_path / "o.mp4"), CONVERT_PRESETS["h264"], None, 1.0)
