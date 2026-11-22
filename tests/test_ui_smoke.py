import os
import sys

import pytest

tk = pytest.importorskip("tkinter")


def _display_ok():
    # Don't probe by creating a throwaway Tk root: a second root crashes Tk 9 on macOS.
    return not sys.platform.startswith("linux") or bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(not _display_ok(), reason="no display available")
def test_window_builds_and_switches_pages(tmp_path):
    from app.core.utils import Settings
    from app.ui.app_window import AppWindow

    win = AppWindow(Settings(tmp_path / "s.json"))
    try:
        win.update()
        win.show_page("convert")
        win.show_page("download")
        page = win.pages["download"]
        page.url_entry.insert(0, "")
        page.fetch()                      # empty URL -> inline error, no crash
        win.update()
        assert "Paste" in page.status.cget("text")
    finally:
        win.destroy()
