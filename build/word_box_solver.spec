# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec – single-file build.
  pyinstaller build/word_box_solver.spec --noconfirm
"""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).parent   # project root
SRC  = ROOT / "src"

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(SRC / "assets"), "assets"),
        (str(SRC / "ml" / "letter_classifier.onnx"), "ml"),
        (str(SRC / "ml" / "class_names.json"), "ml"),
    ],
    hiddenimports=[
        "onnxruntime",
        "cv2",
        "customtkinter",
        "win32gui",
        "win32ui",
        "win32con",
        "pyautogui",
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._win32",
        "PIL",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "torchvision", "torchaudio"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WordBoxSolver",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI app, no console
    onefile=True,
    icon=str(ROOT / 'build' / 'app.ico'),
)
