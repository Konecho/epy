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


def extract_html_title(html_content: bytes) -> str:
    """Extract a human readable title from an HTML document."""
    soup = BeautifulSoup(html_content, "html.parser")
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
    heading = soup.find(["h1", "h2", "h3"])
    if heading:
        return heading.get_text().strip()
    return ""


def build_toc_titles(book) -> dict[str, str]:
    """Map document hrefs to the titles declared in the EPUB TOC (NCX/nav).

    Titles are keyed by both the full normalized href and its basename so that
    differences between manifest hrefs and TOC hrefs do not matter.
    """
    titles: dict[str, str] = {}

    def add(href, title):
        if not href or not isinstance(title, str):
            return
        title = title.strip()
        if not title:
            return
        key = href.split("#")[0].lstrip("/")
        titles[key] = title
        titles[key.split("/")[-1]] = title

    def walk(items):
        for item in items:
            if isinstance(item, (tuple, list)):
                walk(item)
                continue
            add(getattr(item, "href", None), getattr(item, "title", None))
            subitems = getattr(item, "subitems", None)
            if subitems:
                walk(subitems)

    walk(book.toc or [])
    return titles


def _is_nav_document(item) -> bool:
    """Return True for the EPUB navigation/TOC document itself."""
    name = (item.get_name() or "").lower()
    basename = name.split("/")[-1]
    properties = getattr(item, "properties", None) or []
    if isinstance(properties, str):
        properties = [properties]
    return "nav" in properties or basename in {"nav.xhtml", "nav.html", "toc.xhtml", "toc.html"}


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

    # Titles declared in the EPUB table of contents, keyed by href/basename.
    toc_titles = build_toc_titles(book)

    def make_chapter(item):
        """Build a (title, content) pair for a document item."""
        raw = item.get_content()
        content = html_to_text(raw, indent=indent)
        if not content.strip():
            return None
        name = item.get_name() or ""
        item_title = getattr(item, "title", None)
        title = (
            toc_titles.get(name)
            or toc_titles.get(name.lstrip("/"))
            or toc_titles.get(name.split("/")[-1])
            or (item_title.strip() if isinstance(item_title, str) else "")
            or extract_html_title(raw)
            or clean_title(name)
        )
        return (title, content)

    # Parse chapters in spine order, skipping the navigation document.
    chapters = []
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if not item or item.get_type() != 9:  # ITEM_DOCUMENT
            continue
        if _is_nav_document(item):
            continue
        chapter = make_chapter(item)
        if chapter:
            chapters.append(chapter)

    if not chapters:
        # Fallback: try all document items
        for item in book.get_items_of_type(9):
            if _is_nav_document(item):
                continue
            chapter = make_chapter(item)
            if chapter:
                chapters.append(chapter)

    return book_title, chapters
