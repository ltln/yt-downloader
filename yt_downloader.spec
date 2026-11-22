# PyInstaller spec: portable Windows build (onedir, no installer).
from PyInstaller.utils.hooks import collect_data_files

datas = [("app/resources/bin/windows", "resources/bin/windows")]
datas += collect_data_files("customtkinter")

a = Analysis(["app/main.py"], pathex=["."], datas=datas, hiddenimports=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="YTDownloader", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="YTDownloader")
