"""epy - A terminal EPUB reader with vim-like keybindings."""

import curses
import sys
from pathlib import Path

from .progress import get_last_book
from .reader import EpubReader


def main() -> None:
    """Entry point."""
    if len(sys.argv) < 2:
        # Try to open the last book
        last_book = get_last_book()
        if last_book:
            filepath = str(last_book)
        else:
            print("Usage: epy <file.epub>")
            print("  or:  uv run epy <file.epub>")
            sys.exit(1)
    else:
        filepath = sys.argv[1]

    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    if not filepath.lower().endswith(".epub"):
        print(f"Error: Not an EPUB file: {filepath}")
        sys.exit(1)

    try:
        reader = EpubReader(filepath)
        curses.wrapper(reader.run)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
