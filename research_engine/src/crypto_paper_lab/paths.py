"""Path resolution that works in both source and PyInstaller-bundled modes."""

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def data_dir() -> Path:
    """Return the data directory for either source or bundled mode.

    Source: <repo>/research_engine/data
    Bundled: <_MEIPASS>/research_engine/data
    """
    if is_frozen():
        return Path(sys._MEIPASS) / "research_engine" / "data"
    # <repo>/research_engine/src/crypto_paper_lab/paths.py
    # parents[0] = crypto_paper_lab, parents[1] = src, parents[2] = research_engine
    return Path(__file__).resolve().parents[2] / "data"


def research_engine_root() -> Path:
    """Return the research_engine directory (source) or _MEIPASS equivalent (bundled)."""
    if is_frozen():
        return Path(sys._MEIPASS) / "research_engine"
    return Path(__file__).resolve().parents[2]
