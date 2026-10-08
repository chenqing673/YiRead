"""Separate bundled read-only resources from portable user data."""
from pathlib import Path
import sys

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]
RESOURCE_DIR = Path(sys._MEIPASS) if FROZEN else APP_DIR
