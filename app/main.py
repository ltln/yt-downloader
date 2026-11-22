"""Application entry point."""
from __future__ import annotations

import subprocess
import sys


def selftest() -> int:
    """Verify the frozen build works: bundled ffmpeg runs and the GUI can be created. Used by CI."""
    try:
        from app.core.ffmpeg_locator import get_ffmpeg

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if subprocess.run([get_ffmpeg(), "-version"], capture_output=True, creationflags=flags).returncode != 0:
            return 2
        import tempfile
        from pathlib import Path

        from app.core.utils import Settings
        from app.ui.app_window import AppWindow

        win = AppWindow(Settings(Path(tempfile.mkdtemp()) / "settings.json"))
        win.update()
        win.destroy()
        return 0
    except BaseException:  # noqa: BLE001 - windowed exe must not raise a dialog in CI
        return 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    from app.ui.app_window import AppWindow

    AppWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
