# PyInstaller spec for Aegis Clipper.
#
# Builds a single windowed executable (no console) that bundles the engine, web
# dashboard, GSI .cfg template, and — if present — a vendored ffmpeg. The web
# pages live in pages.py (Python strings), so there are no template/static data
# files to chase.
#
# Build:  pyinstaller packaging/aegis.spec   (run from the repo root)
# Output: dist/AegisClipper/AegisClipper.exe
#
# To bundle ffmpeg, drop ffmpeg.exe (and ffprobe.exe) into packaging/vendor/
# before building; otherwise the app falls back to ffmpeg on PATH at runtime.
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.getcwd())

datas = [(os.path.join("cfg", "gamestate_integration_aegis_clipper.cfg"), "cfg")]

# Vendored ffmpeg (optional) — placed next to the exe so resolve_ffmpeg() finds it.
binaries = []
vendor = os.path.join("packaging", "vendor")
for exe in ("ffmpeg.exe", "ffprobe.exe"):
    p = os.path.join(vendor, exe)
    if os.path.exists(p):
        binaries.append((p, "."))

# obsws_python / pystray / webview pull in dynamic backend imports; collect them.
hidden = (
    collect_submodules("obsws_python")
    + collect_submodules("pystray")
    + collect_submodules("webview")
)

a = Analysis(
    ["clipper.py"],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AegisClipper",
    console=False,                      # windowed app; logs go to the tray/dashboard
    icon=os.path.join("packaging", "aegis.ico") if os.path.exists(
        os.path.join("packaging", "aegis.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AegisClipper")
