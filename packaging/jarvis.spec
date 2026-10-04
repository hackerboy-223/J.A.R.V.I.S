# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve().parent.parent

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
    "keyring",
    "mcp",
    "mss",
    "numpy",
    "pyttsx3",
    "sounddevice",
    "vosk",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

hiddenimports.extend(
    [
        "pyttsx3.drivers.sapi5",
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
    excludes=["pytest", "IPython"],
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