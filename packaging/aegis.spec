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
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

# NOTE: PyInstaller resolves paths in a .spec relative to the spec file's own
# directory (packaging/), NOT the cwd. build.ps1 runs from the repo root, so we
# anchor every source path to that root explicitly to avoid "script not found".
ROOT = os.path.abspath(os.getcwd())

datas = [(os.path.join(ROOT, "cfg", "gamestate_integration_aegis_clipper.cfg"), "cfg")]

# pywebview ships runtime JS (webview/js/*.js) that must be bundled, and on
# Windows uses pythonnet (clr) for the EdgeChromium backend. Collect both
# defensively so a missing optional piece doesn't fail the spec on other OSes.
try:
    datas += collect_data_files("webview")
except Exception:
    pass

# Vendored ffmpeg (optional) — placed next to the exe so resolve_ffmpeg() finds it.
binaries = []
vendor = os.path.join(ROOT, "packaging", "vendor")
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
# pythonnet (clr) backs pywebview's EdgeChromium window on Windows.
for pkg in ("clr_loader", "pythonnet"):
    try:
        b, d, h = collect_all(pkg)
        binaries += b
        datas += d
        hidden += h
    except Exception:
        pass

a = Analysis(
    [os.path.join(ROOT, "clipper.py")],
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
    icon=os.path.join(ROOT, "packaging", "aegis.ico") if os.path.exists(
        os.path.join(ROOT, "packaging", "aegis.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AegisClipper")
