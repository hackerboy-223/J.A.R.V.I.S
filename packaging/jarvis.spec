# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, is_module_or_submodule


PROJECT_ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = collect_submodules("jarvis")

# These packages use runtime discovery, native libraries, or package data that
# PyInstaller cannot always infer from static imports.
for package in (
    "comtypes",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "mss",
    "keyring",
    "numpy",
    "pyttsx3",
    "_sounddevice_data",
    "vosk",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

# JARVIS uses MCP as a client library, not the optional MCP command-line
# interface. Collecting all of mcp without a filter imports mcp.cli during the
# PyInstaller analysis phase; mcp.cli requires the optional "typer" dependency
# and aborts the build when mcp[cli] is not installed.
mcp_datas, mcp_binaries, mcp_hiddenimports = collect_all(
    "mcp",
    include_py_files=False,
    filter_submodules=lambda name: not is_module_or_submodule(name, "mcp.cli"),
    on_error="warn once",
)
datas.extend(mcp_datas)
binaries.extend(mcp_binaries)
hiddenimports.extend(mcp_hiddenimports)

hiddenimports.extend(
    [
        "pyttsx3.drivers.sapi5",
        "win32clipboard",
        "win32con",
        "win32gui",
        "win32process",
        "win32com.client",
        "win32com.client.gencache",
    ]
)

analysis = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "mcp.cli"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="J.A.R.V.I.S",
)
