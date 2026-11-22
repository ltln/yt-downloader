from app.core.utils import Settings, fmt_duration, fmt_eta, fmt_speed


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
