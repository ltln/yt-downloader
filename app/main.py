"""Application entry point."""
from __future__ import annotations

import subprocess
import sys


def selftest() -> int:
    """Verify the bundled ffmpeg runs. Used by CI against the built exe."""
    from app.core.ffmpeg_locator import get_ffmpeg

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run([get_ffmpeg(), "-version"], capture_output=True, creationflags=flags)
    return result.returncode


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    # UI is added in a later milestone.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
