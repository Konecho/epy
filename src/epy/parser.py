"""EPUB parsing utilities."""

from pathlib import Path

from ebooklib import epub
from bs4 import BeautifulSoup


def html_to_text(html_content: bytes, indent: bool = True) -> str:
    """Convert HTML content to plain text."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Add indentation to paragraph elements
    if indent:
        for p in soup.find_all('p'):
            # Get current text content
            current = p.get_text().strip()
            if current:
                # Clear and set new text with indent
                p.clear()
                p.append('　　' + current)

    text = soup.get_text(separator="\n")
    # Clean up whitespace
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        elif lines and lines[-1] != "":
            lines.append("")
    return "\n".join(lines)


def clean_title(title: str) -> str:
    """Clean chapter title - remove path and extension."""
    title = title.split("/")[-1]
    title = title.rsplit(".", 1)[0] if "." in title else title
    return title


def parse_epub(filepath: Path, indent: bool = True) -> tuple[str, list[tuple[str, str]]]:
    """Parse EPUB file and return (title, chapters).

    Args:
        filepath: Path to EPUB file.
        indent: Whether to add paragraph indentation.

    Returns:
        Tuple of (book_title, list of (chapter_title, content)).
    """
    book = epub.read_epub(str(filepath))

    # Get book title
    title_meta = book.get_metadata("DC", "title")
    if title_meta:
        book_title = title_meta[0][0] if isinstance(title_meta[0], tuple) else str(title_meta[0])
    else:
        book_title = filepath.stem

    # Parse chapters
    chapters = []
    spine = book.spine
    for item_id, _ in spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == 9:  # ITEM_DOCUMENT
            title = clean_title(item.get_name())
            content = html_to_text(item.get_content(), indent=indent)
            if content.strip():
                chapters.append((title, content))

    if not chapters:
        # Fallback: try all document items
        for item in book.get_items_of_type(9):
            title = clean_title(item.get_name())
            content = html_to_text(item.get_content(), indent=indent)
            if content.strip():
                chapters.append((title, content))

    return book_title, chapters
