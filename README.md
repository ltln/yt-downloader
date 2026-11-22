# YT Downloader

A simple, **portable** Windows app (no installer, no ffmpeg install needed) to:

- **YT Download** - paste a YouTube URL, review the video info, pick video/audio quality and format, download.
- **Convert Video** - convert a local file between formats (e.g. AV1 -> H.264, H.265, VP9, AV1, or extract MP3).

ffmpeg is bundled inside the app. Downloading/extraction is done with [yt-dlp](https://github.com/yt-dlp/yt-dlp), the GUI uses [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Using the app

1. Unzip the build folder anywhere and run `YTDownloader.exe` (Windows may show a SmartScreen warning for unsigned apps: *More info -> Run anyway*).
2. **YT Download** (left sidebar): paste a URL -> *Fetch* -> choose Video/Audio, quality, format, folder -> *Download*.
3. **Convert Video** (GPU-accelerated when possible: NVIDIA NVENC, AMD AMF or Intel Quick Sync are auto-detected for H.264/H.265/AV1; otherwise it uses the CPU. If a GPU encode fails it retries on the CPU automatically): *Choose file* -> pick a target preset and quality -> *Convert*. Output goes next to the original (`name_h264.mp4`) unless you choose a folder; existing files are never overwritten.

Settings are stored in `settings.json` next to the exe (or in `%APPDATA%\YTDownloader` if that folder is read-only).

## Development

```bash
uv venv --python 3.12 .venv          # or any Python 3.10+ with Tk 8.6
uv pip install --python .venv/bin/python -r requirements-dev.txt   # Windows: .venv\Scripts\python
python scripts/fetch_ffmpeg.py        # downloads ffmpeg.exe into app/resources/bin/windows (Windows only)
python -m app.main                    # run the app
python -m pytest                      # tests
pyinstaller yt_downloader.spec        # portable build -> dist/YTDownloader/
```

On non-Windows dev machines, point `FFMPEG_DIR` at a folder containing an `ffmpeg` binary (dev only; shipped builds only use the bundled copy).

CI (`.github/workflows/build.yml`): pull requests run the tests only (no build). When code lands on `main`, CI also builds the portable Windows exe, smoke-tests it and uploads it as the `YTDownloader-windows-x64` workflow artifact (GitHub serves it as a single zip).

## Notes

- YouTube changes often; if downloads start failing, update `yt-dlp` (`pip install -U yt-dlp`) and rebuild.
- Only download content you have the right to download, and respect the terms of service of the sites you use.
