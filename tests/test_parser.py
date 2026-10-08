"""Test EPUB parsing."""

from pathlib import Path
from epy.parser import parse_epub


def create_test_epub(filepath: Path):
    """Create a simple test EPUB file."""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("test123")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    c1 = epub.EpubHtml(title="Introduction", file_name="Text/chap01.xhtml", lang="en")
    c1.content = b"<html><body><h1>Introduction</h1><p>Hello World</p></body></html>"
    c2 = epub.EpubHtml(title="Getting Started", file_name="Text/chap02.xhtml", lang="en")
    c2.content = b"<html><body><h1>Getting Started</h1><p>Content here</p></body></html>"

    book.add_item(c1)
    book.add_item(c2)
    book.toc = [
        epub.Link("Text/chap01.xhtml", "Introduction", "ch1"),
        epub.Link("Text/chap02.xhtml", "Getting Started", "ch2"),
    ]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1, c2]

    epub.write_epub(str(filepath), book)


def test_parse_epub():
    """Test parsing EPUB file."""
    test_file = Path("/tmp/test_parse.epub")
    try:
        create_test_epub(test_file)
        title, chapters = parse_epub(test_file)

        assert title == "Test Book", f"Expected 'Test Book', got '{title}'"
        # The EPUB nav document must be skipped, leaving the two real chapters.
        assert len(chapters) == 2, f"Expected 2 chapters, got {len(chapters)}"
        assert [c[0] for c in chapters] == ["Introduction", "Getting Started"]

        # Check title cleaning
        for ch_title, content in chapters:
            assert ".xhtml" not in ch_title, f"Extension not removed: {ch_title}"
            assert "/" not in ch_title, f"Path not removed: {ch_title}"
            print(f"  ✓ Chapter: '{ch_title}'")

        print("✓ Parse EPUB works")
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_parse_epub()
    print("\nAll tests passed!")
