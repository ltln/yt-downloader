from app.core.utils import Settings, explorer_select_command, fmt_duration, fmt_eta, fmt_speed


def test_formatters():
    assert fmt_duration(65) == "1:05" and fmt_duration(3725) == "1:02:05" and fmt_duration(None) == "--:--"
    assert fmt_speed(512) == "512 B/s" and fmt_speed(2048) == "2.0 KB/s" and fmt_speed(None) == ""
    assert fmt_eta(5) == "ETA 0:05" and fmt_eta(None) == ""


def test_settings_roundtrip(tmp_path):
    p = tmp_path / "sub" / "settings.json"
    s = Settings(p)
    assert s.get("x", 1) == 1
    s.update(x=2)
    assert Settings(p).get("x") == 2


def test_settings_corrupt_file(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json")
    assert Settings(p).get("a", "d") == "d"


def test_explorer_select_command_quotes_only_the_path():
    cmd = explorer_select_command(r"C:/Users/me/Downloads\Some Video [abc].mp4")
    assert cmd == 'explorer /select,"C:\\Users\\me\\Downloads\\Some Video [abc].mp4"'


def test_open_folder_windows_selects_file(tmp_path, monkeypatch):
    from app.core import utils
    f = tmp_path / "my video.mp4"
    f.write_text("x")
    calls = []
    monkeypatch.setattr(utils.sys, "platform", "win32")
    monkeypatch.setattr(utils.subprocess, "Popen", lambda cmd, *a, **k: calls.append(cmd))
    utils.open_folder(str(f), select_file=True)
    assert isinstance(calls[0], str) and calls[0].startswith('explorer /select,"') and "my video.mp4" in calls[0]


def test_open_folder_missing_file_opens_parent(tmp_path, monkeypatch):
    from app.core import utils
    calls = []
    monkeypatch.setattr(utils.sys, "platform", "darwin")
    monkeypatch.setattr(utils.subprocess, "Popen", lambda cmd, *a, **k: calls.append(cmd))
    utils.open_folder(str(tmp_path / "gone.mp4"), select_file=True)
    assert calls == [["open", str(tmp_path)]]
