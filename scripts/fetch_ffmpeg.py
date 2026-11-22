"""Download a static Windows ffmpeg build and place ffmpeg.exe/ffprobe.exe in app/resources/bin/windows."""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
       "ffmpeg-master-latest-win64-gpl.zip")
DEST = Path(__file__).resolve().parent.parent / "app" / "resources" / "bin" / "windows"
WANTED = {"ffmpeg.exe", "ffprobe.exe"}


def main() -> int:
    if all((DEST / n).is_file() for n in WANTED) and "--force" not in sys.argv:
        print(f"ffmpeg already present in {DEST}")
        return 0
    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL, timeout=120) as resp:
        data = resp.read()
    DEST.mkdir(parents=True, exist_ok=True)
    found = set()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            name = member.rsplit("/", 1)[-1]
            if name in WANTED and "/bin/" in member:
                (DEST / name).write_bytes(zf.read(member))
                found.add(name)
    missing = WANTED - found
    if missing:
        print(f"ERROR: missing in archive: {missing}", file=sys.stderr)
        return 1
    print(f"Installed {sorted(found)} to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
