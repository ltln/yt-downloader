import threading
import pytest
from app.core import downloader as dl
from app.core.presets import DownloadSettings


def test_parse_info_heights():
    raw = {"title": "T", "uploader": "U", "duration": 10, "thumbnail": "http://x/t.jpg",
           "formats": [{"height": 360, "vcodec": "avc1"}, {"height": 1080, "vcodec": "vp9"},
                       {"height": 1080, "vcodec": "av01"}, {"height": None, "vcodec": "none"},
                       {"height": 720, "vcodec": "none"}]}
    info = dl.parse_info("http://u", raw)
    assert info.heights == [1080, 360] and info.title == "T" and info.channel == "U"


def test_fetch_info_rejects_non_url():
    with pytest.raises(dl.DownloadFailed):
        dl.fetch_info("hello world")


@pytest.mark.parametrize("msg,expected", [
    ("ERROR: Private video. Sign in", "private"),
    ("ERROR: Unsupported URL: foo", "valid video URL"),
    ("ERROR: [youtube] x: Video unavailable", "unavailable"),
    ("<urlopen error [Errno 8] getaddrinfo failed>", "Network"),
])
def test_friendly_error(msg, expected):
    assert expected.lower() in dl.friendly_error(Exception(msg)).lower()


def test_opts_video_and_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "get_ffmpeg_dir", lambda: "/ff")
    v = dl.build_ydl_opts(DownloadSettings(height=720, container="mp4", out_dir=str(tmp_path)))
    assert v["merge_output_format"] == "mp4" and v["ffmpeg_location"] == "/ff"
    assert v["paths"]["home"] == str(tmp_path) and "postprocessors" not in v
    a = dl.build_ydl_opts(DownloadSettings(kind="audio", audio_format="m4a"))
    assert a["postprocessors"][0]["preferredcodec"] == "m4a" and "merge_output_format" not in a


def test_progress_hook_reports_and_cancels(monkeypatch):
    monkeypatch.setattr(dl, "get_ffmpeg_dir", lambda: "/ff")
    seen = []
    cancel = threading.Event()
    opts = dl.build_ydl_opts(DownloadSettings(), seen.append, cancel)
    hook = opts["progress_hooks"][0]
    hook({"status": "downloading", "filename": "a", "downloaded_bytes": 50, "total_bytes": 100, "speed": 10, "eta": 5})
    hook({"status": "downloading", "filename": "b", "downloaded_bytes": 10, "total_bytes": 100})
    assert [(p.percent, p.part) for p in seen] == [(50.0, 1), (10.0, 2)]
    cancel.set()
    with pytest.raises(dl.DownloadCancelled):
        hook({"status": "downloading", "filename": "b"})
