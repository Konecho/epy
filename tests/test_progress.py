"""Test progress persistence."""

from epy.progress import load_progress, save_progress, get_book_id, DATA_DIR
from pathlib import Path


def test_save_and_load():
    """Test saving and loading progress."""
    test_id = "/test/book.epub"
    save_progress(test_id, 2, 15)
    progress = load_progress(test_id)
    assert progress["chapter"] == 2
    assert progress["scroll"] == 15
    assert "last_opened" in progress
    print("✓ Save and load works")


def test_nonexistent():
    """Test loading non-existent progress."""
    progress = load_progress("/nonexistent/book.epub")
    assert progress is None
    print("✓ Non-existent returns None")


def test_overwrite():
    """Test overwriting progress."""
    test_id = "/test/overwrite.epub"
    save_progress(test_id, 0, 0)
    save_progress(test_id, 3, 50)
    progress = load_progress(test_id)
    assert progress["chapter"] == 3
    assert progress["scroll"] == 50
    print("✓ Overwrite works")


if __name__ == "__main__":
    test_save_and_load()
    test_nonexistent()
    test_overwrite()
    print(f"\nData directory: {DATA_DIR}")
    print("All tests passed!")
