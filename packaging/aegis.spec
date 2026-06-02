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

# NOTE: PyInstaller runs a .spec with the cwd set to the spec file's own folder,
# so os.getcwd() is packaging/, NOT the repo root. PyInstaller injects SPECPATH
# (the spec's directory) as a global; the repo root is its parent. Anchor every
# source path to that so "clipper.py", "cfg/", and "vendor/" resolve correctly.
ROOT = os.path.dirname(os.path.abspath(SPECPATH))

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

# Embed Windows version metadata (CompanyName/ProductName/version). An exe with
# no version resource looks more suspicious to antivirus heuristics and shows
# "Unknown publisher"; real metadata is basic hygiene. (It does NOT replace code
# signing — only a certificate removes the SmartScreen prompt.)
version_obj = None
try:
    import re as _re
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
        VarFileInfo, VarStruct,
    )
    _vtext = open(os.path.join(ROOT, "aegis", "__init__.py"), encoding="utf-8").read()
    _ver = _re.search(r'__version__\s*=\s*"([^"]+)"', _vtext).group(1)
    _vt = tuple(int(x) for x in (_ver.split(".") + ["0", "0", "0"])[:4])
    version_obj = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_vt, prodvers=_vt),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "Aegis Clipper"),
                StringStruct("FileDescription", "Aegis Clipper — automatic CS2 highlight clipper"),
                StringStruct("FileVersion", _ver),
                StringStruct("InternalName", "AegisClipper"),
                StringStruct("OriginalFilename", "AegisClipper.exe"),
                StringStruct("ProductName", "Aegis Clipper"),
                StringStruct("ProductVersion", _ver),
                StringStruct("LegalCopyright", "MIT License"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
    _vpath = os.path.join(ROOT, "packaging", "_version_info.txt")
    with open(_vpath, "w", encoding="utf-8") as _f:
        _f.write(str(version_obj))
    version_obj = _vpath
except Exception:
    version_obj = None

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
    version=version_obj,                # embedded Windows version metadata
    icon=os.path.join(ROOT, "packaging", "aegis.ico") if os.path.exists(
        os.path.join(ROOT, "packaging", "aegis.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AegisClipper")
