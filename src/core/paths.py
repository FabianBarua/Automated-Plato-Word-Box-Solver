"""Centralized path resolution for dev mode and PyInstaller --onefile."""

import sys
from pathlib import Path


def _base_dir() -> Path:
    """Return the directory where bundled data files live.

    - Frozen (--onefile): sys._MEIPASS  (temp extraction folder)
    - Dev:                 src/          (parent of this file's parent)
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent  # core/ -> src/


def _exe_dir() -> Path:
    """Return the directory where the .exe actually lives (for external tools).

    - Frozen: directory containing the .exe
    - Dev:    project root  (two levels up from src/core/)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent  # src/core -> src -> project root


# ── Public paths ───────────────────────────────────────────────────

ASSETS_DIR = _base_dir() / "assets"
DATA_DIR = ASSETS_DIR / "data"
FONTS_DIR = ASSETS_DIR / "fonts" / "Poppins"
ML_DIR = _base_dir() / "ml"
SCREENSHOT_DIR = _base_dir() / "screenshots"
TOOLS_DIR = _exe_dir() / "tools"
