"""Reading progress persistence."""

import json
import time
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "epy"
SETTINGS_FILE = DATA_DIR / "settings.json"


def get_book_id(filepath: Path) -> str:
    """Generate a unique ID for a book based on its absolute path."""
    return str(filepath.resolve())


def load_progress(book_id: str) -> dict | None:
    """Load reading progress for a book."""
    progress_file = DATA_DIR / "progress.json"
    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(book_id)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def save_progress(book_id: str, chapter: int, scroll: int):
    """Save reading progress for a book."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = DATA_DIR / "progress.json"

    data = {}
    if progress_file.exists():
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    data[book_id] = {
        "chapter": chapter,
        "scroll": scroll,
        "last_opened": time.time(),
    }

    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get_last_book() -> Path | None:
    """Get the path of the last opened book."""
    progress_file = DATA_DIR / "progress.json"
    if not progress_file.exists():
        return None

    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not data:
        return None

    # Find the most recently opened book
    last_book_id = None
    last_time = 0
    for book_id, info in data.items():
        opened = info.get("last_opened", 0)
        if opened > last_time:
            last_time = opened
            last_book_id = book_id

    if last_book_id:
        path = Path(last_book_id)
        if path.exists():
            return path

    return None


def load_settings() -> dict:
    """Load global settings."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_settings(settings: dict):
    """Save global settings."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
