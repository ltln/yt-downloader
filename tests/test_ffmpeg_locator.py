import sys
import pytest
from app.core import ffmpeg_locator as fl


def test_finds_bundled_when_present(tmp_path, monkeypatch):
    exe = f"ffmpeg{fl._EXE}"
    (tmp_path / exe).write_text("x")
    monkeypatch.setattr(fl, "_bundled_dir", lambda: tmp_path)
    assert fl.get_ffmpeg() == str(tmp_path / exe)
    assert fl.get_ffmpeg_dir() == str(tmp_path)


def test_frozen_never_uses_path(tmp_path, monkeypatch):
    monkeypatch.setattr(fl, "_bundled_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(fl.shutil, "which", lambda n: "/usr/bin/" + n)
    with pytest.raises(FileNotFoundError):
        fl.get_ffmpeg()


def test_dev_env_fallback(tmp_path, monkeypatch):
    exe = f"ffmpeg{fl._EXE}"
    (tmp_path / exe).write_text("x")
    monkeypatch.setattr(fl, "_bundled_dir", lambda: tmp_path / "nope")
    monkeypatch.setenv("FFMPEG_DIR", str(tmp_path))
    assert fl.get_ffmpeg() == str(tmp_path / exe)
