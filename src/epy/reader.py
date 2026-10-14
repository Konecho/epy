"""Terminal UI for EPUB reader."""

import curses
import time
import unicodedata
from pathlib import Path

from .parser import parse_epub
from .progress import get_book_id, load_progress, save_progress, load_settings, save_settings, list_history

# Color themes: (name, text_fg, text_bg, bg, status_fg, status_bg)
# Colors: -1=default, 0=black, 1=red, 2=green, 3=yellow, 4=blue, 5=magenta, 6=cyan, 7=white
THEMES = [
    # (name, text_fg, text_bg, bg, status_fg, status_bg)
    ("Default", -1, -1, -1, -1, -1),
    ("White/Black", curses.COLOR_BLACK, curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_BLACK),
    ("Black/White", curses.COLOR_WHITE, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_WHITE),
    ("Green/Black", curses.COLOR_GREEN, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_GREEN, curses.COLOR_BLACK),
    ("Cyan/Black", curses.COLOR_CYAN, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_CYAN, curses.COLOR_BLACK),
    ("Yellow/Black", curses.COLOR_YELLOW, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_YELLOW, curses.COLOR_BLACK),
    ("White/Blue", curses.COLOR_WHITE, curses.COLOR_BLUE, curses.COLOR_BLUE, curses.COLOR_WHITE, curses.COLOR_BLUE),
    ("White/Green", curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_GREEN, curses.COLOR_WHITE, curses.COLOR_GREEN),
    ("Black/Cyan", curses.COLOR_BLACK, curses.COLOR_CYAN, curses.COLOR_CYAN, curses.COLOR_BLACK, curses.COLOR_CYAN),
    ("White/Red", curses.COLOR_WHITE, curses.COLOR_RED, curses.COLOR_RED, curses.COLOR_WHITE, curses.COLOR_RED),
    ("Magenta/Black", curses.COLOR_MAGENTA, curses.COLOR_BLACK, curses.COLOR_BLACK, curses.COLOR_MAGENTA, curses.COLOR_BLACK),
]


class EpubReader:
    """Terminal EPUB reader using curses."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.book_id = get_book_id(self.filepath)
        self.book_title: str = ""
        self.chapters: list[tuple[str, str]] = []  # (title, content)
        self.current_chapter = 0
        self.scroll_offset = 0
        self.max_scroll = 0
        self.show_toc = False
        self.current_theme = 0
        self.toc_selection = 0
        self.message = ""
        self.show_bookshelf = False
        self.history: list[dict] = []
        self.shelf_selection = 0
        self.height = 0
        self.width = 0
        self.at_end = False  # Whether we're at the end of current chapter
        self.at_start = False  # Whether we're at the start of current chapter
        self.toc_input = ""  # Number input for TOC jump

        # Search state
        self.searching = False  # Whether the search prompt is active
        self.search_input = ""  # Query being typed
        self.search_query = ""  # Last executed query
        self.search_results: list[dict] = []  # [{chapter, line, text}]
        self.show_search_results = False
        self.search_selection = 0

        # Load settings
        settings = load_settings()
        self.show_status_bar = settings.get("show_status_bar", True)
        self.show_progress_bar = settings.get("show_progress_bar", False)

        # Cache of wrapped line counts per chapter, keyed by terminal width.
        self._line_counts: list[int] | None = None
        self._line_counts_width: int | None = None

        self._load_book()
        self._restore_progress()

    def _load_book(self):
        """Load and parse the EPUB file."""
        self.book_title, self.chapters = parse_epub(self.filepath)

    def _open_book(self, filepath: str | Path) -> bool:
        """Switch to another EPUB, saving the current position first."""
        path = Path(filepath)
        try:
            book_title, chapters = parse_epub(path)
        except Exception as exc:  # noqa: BLE001 - surface any parse failure
            self.message = f"Cannot open: {exc}"
            return False

        self._save_current_progress()
        self.filepath = path
        self.book_id = get_book_id(path)
        self.book_title = book_title
        self.chapters = chapters
        self.current_chapter = 0
        self.scroll_offset = 0
        self.toc_selection = 0
        self.toc_input = ""
        self.search_input = ""
        self.search_results = []
        self.show_search_results = False
        self.search_selection = 0
        self._line_counts = None
        self._line_counts_width = None
        self._restore_progress()
        self.message = f"Opened: {self.book_title}"
        self._save_current_progress()
        return True

    def _restore_progress(self):
        """Restore reading progress from saved state."""
        progress = load_progress(self.book_id)
        if progress:
            chapter = progress.get("chapter", 0)
            scroll = progress.get("scroll", 0)
            # Prefer matching the saved chapter title so that the position
            # survives changes to the parsed chapter list.
            saved_title = progress.get("title")
            if saved_title:
                for idx, (title, _) in enumerate(self.chapters):
                    if title == saved_title:
                        chapter = idx
                        break
            if 0 <= chapter < len(self.chapters):
                self.current_chapter = chapter
                self.scroll_offset = scroll
                self.message = f"Restored: Chapter {chapter + 1}"

    def _save_current_progress(self):
        """Save current reading progress."""
        title = ""
        if 0 <= self.current_chapter < len(self.chapters):
            title = self.chapters[self.current_chapter][0]
        save_progress(
            self.book_id,
            self.current_chapter,
            self.scroll_offset,
            title,
            self.book_title,
            self._current_percent(),
        )

    def _visible_height(self) -> int:
        """Number of content rows for the current status-bar setting."""
        return self.height - 1 if self.show_status_bar else self.height

    def _current_percent(self) -> int | None:
        """Whole-book reading percentage at the current position."""
        visible_height = self._visible_height()
        if not self.width or not visible_height or not self.chapters:
            return None
        return int(round(self._overall_progress(self.width, visible_height) * 100))

    def _apply_theme(self, stdscr):
        """Apply the current color theme."""
        name, text_fg, text_bg, bg, status_fg, status_bg = THEMES[self.current_theme]
        self.message = f"Theme: {name}"

        if text_fg == -1 and text_bg == -1:
            # Default theme - use terminal defaults
            curses.use_default_colors()
            curses.init_pair(1, -1, -1)  # text
            curses.init_pair(2, -1, -1)  # status
            stdscr.bkgd(" ")
        else:
            curses.init_pair(1, text_fg, text_bg)  # text
            curses.init_pair(2, status_fg, status_bg)  # status
            stdscr.bkgd(" ", curses.color_pair(2))

    def _get_lines(self, chapter_idx: int) -> list[str]:
        """Get lines for a chapter."""
        if 0 <= chapter_idx < len(self.chapters):
            return self.chapters[chapter_idx][1].split("\n")
        return []

    def _draw_status_bar(self, stdscr, height: int, width: int):
        """Draw the status bar at the bottom."""
        chapter_title = self.chapters[self.current_chapter][0] if self.chapters else ""
        chapter_num = f"Ch {self.current_chapter + 1}/{len(self.chapters)}"

        # Calculate reading progress percentage
        if self.max_scroll > 0:
            percent = int(self.scroll_offset / self.max_scroll * 100)
            progress = f"{percent}%"
        else:
            progress = "100%"

        status = f" {self.book_title} | {chapter_title} | {chapter_num} | {progress} "
        if self.message:
            status = f" {self.message} "
            self.message = ""

        try:
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(height - 1, 0, self._fit(status, width - 1))
            stdscr.attroff(curses.color_pair(2))
        except curses.error:
            pass

    def _draw_end_marker(self, stdscr, height: int, width: int):
        """Draw END marker when at end of chapter."""
        if self.at_end:
            y = height - 2 if self.show_status_bar else height - 1
            try:
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(y, width // 2 - 3, " [END] ")
                stdscr.attroff(curses.A_BOLD)
            except curses.error:
                pass

    def _draw_start_marker(self, stdscr, height: int, width: int):
        """Draw the chapter number and START marker when at chapter start."""
        if self.at_start:
            marker = f" Ch {self.current_chapter + 1} [START] "
            x = max(0, (width - self._str_width(marker)) // 2)
            try:
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(0, x, marker)
                stdscr.attroff(curses.A_BOLD)
            except curses.error:
                pass

    def _draw_progress_bar(self, stdscr, height: int, width: int):
        """Underline part of the last visible line to show book-wide progress."""
        if not self.show_progress_bar:
            return

        visible_height = height - 1 if self.show_status_bar else height
        y = visible_height - 1  # last content row
        progress = self._overall_progress(width, visible_height)
        bar_max = self._text_width(width)
        bar_len = min(bar_max, int(round(progress * bar_max)))
        if bar_len <= 0:
            return
        # Never touch the bottom-right cell, which curses refuses to write to.
        if y == height - 1:
            bar_len = min(bar_len, width - 1)

        try:
            stdscr.chgat(y, 0, bar_len, curses.color_pair(1) | curses.A_UNDERLINE)
        except curses.error:
            pass

    def _draw_chapter_bar(self, stdscr, height: int, width: int):
        """Fill the rightmost column to show progress within the chapter."""
        if not self.show_progress_bar or width < 2:
            return

        visible_height = height - 1 if self.show_status_bar else height
        progress = self._chapter_progress(width, visible_height)
        filled = int(round(progress * visible_height))
        attr = curses.color_pair(1) | curses.A_REVERSE
        x = width - 1
        for y in range(min(filled, visible_height)):
            try:
                stdscr.chgat(y, x, 1, attr)
            except curses.error:
                pass

    def _chapter_line_counts(self, width: int) -> list[int]:
        """Number of wrapped display lines per chapter (cached by text width)."""
        text_width = self._text_width(width)
        if self._line_counts is not None and self._line_counts_width == text_width:
            return self._line_counts

        counts = []
        for _, content in self.chapters:
            count = 0
            for line in content.split("\n"):
                if not line:
                    count += 1
                else:
                    count += len(self._wrap_line(line, text_width))
            counts.append(count)

        self._line_counts = counts
        self._line_counts_width = text_width
        return counts

    def _overall_progress(self, width: int, visible_height: int) -> float:
        """Fraction (0.0-1.0) of the whole book read at the current position."""
        counts = self._chapter_line_counts(width)
        total = sum(counts)
        if total <= 0:
            return 1.0
        read = sum(counts[: self.current_chapter]) + self.scroll_offset + visible_height
        return max(0.0, min(1.0, read / total))

    def _chapter_progress(self, width: int, visible_height: int) -> float:
        """Fraction (0.0-1.0) of the current chapter read."""
        counts = self._chapter_line_counts(width)
        if not (0 <= self.current_chapter < len(counts)):
            return 1.0
        total = counts[self.current_chapter]
        if total <= 0:
            return 1.0
        read = self.scroll_offset + visible_height
        return max(0.0, min(1.0, read / total))

    def _draw_help(self, stdscr, height: int, width: int):
        """Draw help overlay."""
        help_lines = [
            "EPUB Reader - Keybindings",
            "",
            "  h / ←    Page up",
            "  l / →    Page down",
            "  j / ↓    Scroll down",
            "  k / ↑    Scroll up",
            "  n        Next chapter",
            "  p        Previous chapter",
            "  Tab      Toggle table of contents",
            "  /        Search in the book",
            "  s        Toggle status bar",
            "  b        Toggle progress bars (book + chapter)",
            "  H        Open bookshelf (reading history)",
            "  c        Cycle color theme",
            "  g        Go to first line",
            "  G        Go to last line",
            "  ?        Show this help",
            "  q        Quit",
            "",
            "Press any key to close help",
        ]

        start_y = max(0, (height - len(help_lines)) // 2)
        start_x = max(0, (width - 40) // 2)

        try:
            for i, line in enumerate(help_lines):
                y = start_y + i
                if y >= height - 1:
                    break
                padded = f" {line:<38} "
                stdscr.addstr(y, start_x, padded[:min(40, width - start_x)])
        except curses.error:
            pass

    def _draw_toc(self, stdscr, height: int, width: int):
        """Draw table of contents overlay."""
        visible_height = height - 4  # Reserve space for input line
        toc_start = max(0, self.toc_selection - visible_height + 2)

        try:
            # Title
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(1, 0, " Table of Contents ".center(width)[:width])
            stdscr.attroff(curses.A_REVERSE)
            stdscr.addstr(2, 0, "─" * width)

            for i in range(visible_height):
                idx = toc_start + i
                y = 3 + i
                if y >= height - 2 or idx >= len(self.chapters):
                    break

                num = f"{idx + 1:>3}."
                title = self.chapters[idx][0]
                # Highlight selection
                prefix = ">> " if idx == self.toc_selection else "   "
                is_current = idx == self.current_chapter
                marker = " *" if is_current else "  "

                line = f"{prefix}{num} {title}{marker}"
                line = self._fit(line, width)

                if idx == self.toc_selection:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, 0, line)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, 0, line)

            # Input line at bottom
            input_y = height - 2
            if self.toc_input:
                stdscr.addstr(input_y, 0, self._fit(f" Go to: {self.toc_input}_", width))
            else:
                stdscr.addstr(input_y, 0, self._fit(" ↑/↓ Select  Enter: Jump  Tab/Esc: Back ", width))
        except curses.error:
            pass

    def _snippet(self, text: str, query: str, width: int) -> str:
        """Return a short excerpt of text with the match kept visible."""
        if width <= 0 or not text:
            return ""
        lower = text.lower()
        pos = lower.find(query.lower())
        if pos < 0:
            pos = 0
        # Keep a little leading context, measured in display columns so wide
        # characters (CJK) do not push the match out of view.
        budget = max(0, min(8, width // 4))
        start = pos
        used = 0
        while start > 0:
            char_w = self._char_width(text[start - 1])
            if used + char_w > budget:
                break
            used += char_w
            start -= 1
        excerpt = text[start:start + max(width, 20) * 2]
        prefix = "…" if start > 0 else ""
        return prefix + excerpt

    def _draw_search_prompt(self, stdscr, height: int, width: int):
        """Draw the search input prompt on the bottom row."""
        y = height - 1
        prompt = f" Search: {self.search_input}_"
        if self.search_input:
            prompt = f" Search: {self.search_input}_  (Enter: search  Esc: cancel) "
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(y, 0, self._fit(prompt, width - 1))
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

    def _run_search(self):
        """Search all chapters for the typed query and build result list."""
        query = self.search_input.strip()
        self.searching = False
        self.search_input = ""
        if not query:
            return

        needle = query.lower()
        results: list[dict] = []
        max_results = 500
        for chapter_idx, (_, content) in enumerate(self.chapters):
            for line_idx, raw in enumerate(content.split("\n")):
                if needle in raw.lower():
                    results.append({"chapter": chapter_idx, "line": line_idx, "text": raw})
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        self.search_query = query
        self.search_results = results
        if not results:
            self.message = f"No matches: {query}"
            return
        self.show_search_results = True
        self.search_selection = 0
        self.message = f"{len(results)} matches for '{query}'"

    def _display_offset_for_line(self, chapter_idx: int, raw_idx: int, query: str = "") -> int:
        """Display-line offset of a raw content line after wrapping."""
        text_width = self._text_width(self.width)
        raw_lines = self._get_lines(chapter_idx)
        offset = 0
        for i in range(min(raw_idx, len(raw_lines))):
            line = raw_lines[i]
            if not line:
                offset += 1
            else:
                offset += len(self._wrap_line(line, text_width))

        # Point at the wrapped segment that actually holds the match.
        if query and 0 <= raw_idx < len(raw_lines):
            raw = raw_lines[raw_idx]
            segments = self._wrap_line(raw, text_width) if raw else [""]
            needle = query.lower()
            for skip, segment in enumerate(segments):
                if needle in segment.lower():
                    offset += skip
                    break
        return offset

    def _jump_to_result(self):
        """Jump to the currently selected search result."""
        if not (0 <= self.search_selection < len(self.search_results)):
            return
        result = self.search_results[self.search_selection]
        chapter_idx = result["chapter"]
        if not (0 <= chapter_idx < len(self.chapters)):
            return
        if self.width <= 0:
            self.width = 80
        self.current_chapter = chapter_idx
        self.scroll_offset = self._display_offset_for_line(chapter_idx, result["line"], self.search_query)
        self.show_search_results = False
        self.message = f"Match {self.search_selection + 1}/{len(self.search_results)}"
        self._save_current_progress()

    def _match_segments(self, text: str, query: str) -> list[tuple[str, bool]]:
        """Split text into ``(piece, is_match)`` segments for highlighting."""
        if not query or not text:
            return [(text, False)]
        lower = text.lower()
        needle = query.lower()
        if not needle or len(lower) != len(text) or needle not in lower:
            return [(text, False)]

        segments: list[tuple[str, bool]] = []
        pos = 0
        while True:
            found = lower.find(needle, pos)
            if found < 0:
                break
            if found > pos:
                segments.append((text[pos:found], False))
            segments.append((text[found:found + len(needle)], True))
            pos = found + len(needle)
        if pos < len(text):
            segments.append((text[pos:], False))
        return segments or [(text, False)]

    def _draw_result_line(self, stdscr, y: int, width: int,
                          segments: list[tuple[str, bool]], selected: bool):
        """Draw one search-result row, reverse-highlighting the matches."""
        if selected:
            # Reverse the whole selected row, then punch the matches out so
            # they still stand out against the highlighted selection.
            line = self._fit("".join(text for text, _ in segments), width)
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(y, 0, line)
            stdscr.attroff(curses.A_REVERSE)
            x = 0
            for text, is_match in segments:
                seg_width = self._str_width(text)
                if is_match and seg_width > 0 and x + seg_width <= width:
                    stdscr.chgat(y, x, seg_width, curses.color_pair(1))
                x += seg_width
        else:
            x = 0
            for text, is_match in segments:
                if x >= width:
                    return
                seg_width = self._str_width(text)
                piece = text if x + seg_width <= width else self._fit(text, width - x).rstrip()
                if is_match and piece:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, x, piece)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, x, piece)
                x += self._str_width(piece)
            pad = width - x
            if pad > 0:
                stdscr.addstr(y, x, " " * pad)

    def _draw_search_results(self, stdscr, height: int, width: int):
        """Draw the search results list (TOC-like overlay)."""
        visible_height = max(0, height - 4)
        start = max(0, self.search_selection - visible_height + 2)

        try:
            header = f" Search: {self.search_query} - {len(self.search_results)} matches "
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(1, 0, self._fit(header.center(width), width))
            stdscr.attroff(curses.A_REVERSE)
            stdscr.addstr(2, 0, self._fit("─" * width, width))

            for i in range(visible_height):
                idx = start + i
                y = 3 + i
                if y >= height - 2 or idx >= len(self.search_results):
                    break

                result = self.search_results[idx]
                selected = idx == self.search_selection
                prefix = ">> " if selected else "   "
                num = f"{idx + 1:>3}."
                tail = f"  ch.{result['chapter'] + 1}"
                snippet_width = max(0, width - self._str_width(prefix) - self._str_width(num)
                                    - 1 - self._str_width(tail))
                snippet = self._snippet(result["text"], self.search_query, snippet_width)
                snippet = self._fit(snippet, snippet_width).rstrip()
                segments = [
                    (f"{prefix}{num} ", False),
                    *self._match_segments(snippet, self.search_query),
                    (tail, False),
                ]
                self._draw_result_line(stdscr, y, width, segments, selected)

            stdscr.addstr(height - 2, 0, self._fit(" ↑/↓ Select  Enter: Jump  /: New search  Esc: Back ", width))
        except curses.error:
            pass

    def _format_ago(self, timestamp: float) -> str:
        """Format a timestamp as a short relative time."""
        if not timestamp:
            return ""
        seconds = int(time.time() - timestamp)
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        return f"{days // 365}y ago"

    def _draw_bookshelf(self, stdscr, height: int, width: int):
        """Draw the reading-history bookshelf overlay."""
        visible_height = max(0, height - 4)
        start = max(0, self.shelf_selection - visible_height + 2)

        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(1, 0, self._fit(" Bookshelf - History ".center(width), width))
            stdscr.attroff(curses.A_REVERSE)
            stdscr.addstr(2, 0, self._fit("─" * width, width))

            if not self.history:
                stdscr.addstr(3, 0, self._fit(" (no history yet) ", width))

            for i in range(visible_height):
                idx = start + i
                y = 3 + i
                if y >= height - 2 or idx >= len(self.history):
                    break

                item = self.history[idx]
                prefix = ">> " if idx == self.shelf_selection else "   "
                percent = item.get("percent")
                pct = f"{percent:>3}%" if isinstance(percent, int) else "   -"
                tail = f"{pct}  ch.{item.get('chapter', 0) + 1}  {self._format_ago(item.get('last_opened', 0))}"
                title_width = max(0, width - self._str_width(prefix) - self._str_width(tail) - 2)
                title = self._fit(item.get("title", ""), title_width)
                line = self._fit(f"{prefix}{title}  {tail}", width)

                if idx == self.shelf_selection:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, 0, line)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, 0, line)

            stdscr.addstr(height - 2, 0, self._fit(" ↑/↓ Select  Enter: Open  Esc/Tab: Back ", width))
        except curses.error:
            pass

    def _char_width(self, char: str) -> int:
        """Get display width of a character (2 for CJK, 1 for others)."""
        if char == '\t':
            return 4
        eaw = unicodedata.east_asian_width(char)
        if eaw in ('F', 'W'):
            return 2
        return 1

    def _str_width(self, s: str) -> int:
        """Get display width of a string."""
        return sum(self._char_width(c) for c in s)

    def _fit(self, s: str, width: int) -> str:
        """Truncate a string to display width and pad it with spaces."""
        result = []
        current = 0
        for char in s:
            char_w = self._char_width(char)
            if current + char_w > width:
                break
            result.append(char)
            current += char_w
        return "".join(result) + " " * max(0, width - current)

    def _text_width(self, width: int) -> int:
        """Usable text width, reserving the last column for the chapter bar."""
        if self.show_progress_bar and width > 1:
            return width - 1
        return width

    def _wrap_line(self, line: str, width: int) -> list[str]:
        """Wrap a line to fit within width, breaking at word boundaries."""
        if self._str_width(line) <= width:
            return [line]

        wrapped = []
        while line:
            if self._str_width(line) <= width:
                wrapped.append(line)
                break

            # Find break point by accumulating width
            current_width = 0
            break_at = 0
            last_space_at = 0
            last_space_width = 0

            for i, char in enumerate(line):
                char_w = self._char_width(char)
                if current_width + char_w > width:
                    break
                current_width += char_w
                break_at = i + 1
                if char == ' ':
                    last_space_at = i + 1
                    last_space_width = current_width

            # Prefer breaking at space if it's past halfway
            if last_space_at > break_at // 2 and last_space_at > 0:
                break_at = last_space_at

            if break_at == 0:
                # No valid break point, force at least one char
                break_at = 1

            wrapped.append(line[:break_at])
            line = line[break_at:].lstrip()

        return wrapped

    def _draw_content(self, stdscr, height: int, width: int):
        """Draw chapter content."""
        raw_lines = self._get_lines(self.current_chapter)
        visible_height = height - 1 if self.show_status_bar else height
        text_width = self._text_width(width)

        # Pre-wrap all lines and build display lines
        display_lines = []
        for line in raw_lines:
            if not line:
                display_lines.append("")
            else:
                display_lines.extend(self._wrap_line(line, text_width))

        # Ensure scroll_offset is valid - allow scrolling until last line is visible
        max_offset = max(0, len(display_lines) - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
        self.max_scroll = max_offset

        # Check if at start or end
        self.at_start = self.scroll_offset == 0
        self.at_end = self.scroll_offset >= max_offset

        # Keep the first row free for the [START] marker so it never covers the
        # chapter text.
        top_row = 1 if self.at_start else 0
        for i in range(visible_height - top_row):
            line_idx = self.scroll_offset + i
            if line_idx >= len(display_lines):
                break

            line = display_lines[line_idx]
            try:
                stdscr.addstr(top_row + i, 0, line[:text_width], curses.color_pair(1))
            except curses.error:
                pass

    def _next_chapter(self):
        """Switch to next chapter."""
        if self.current_chapter < len(self.chapters) - 1:
            self.current_chapter += 1
            self.scroll_offset = 0
            self.message = f"Chapter {self.current_chapter + 1}"
            return True
        return False

    def _prev_chapter(self):
        """Switch to previous chapter and go to start."""
        if self.current_chapter > 0:
            self.current_chapter -= 1
            self.scroll_offset = 0
            self.message = f"Chapter {self.current_chapter + 1}"
            return True
        return False

    def _prev_chapter_end(self):
        """Switch to previous chapter and go to end."""
        if self.current_chapter > 0:
            self.current_chapter -= 1
            # Set scroll to a large value, it will be clamped in _draw_content
            self.scroll_offset = 999999
            self.message = f"Chapter {self.current_chapter + 1}"
            return True
        return False

    def _read_key(self, stdscr):
        """Read one key as ``(numeric_key, raw)``.

        ``raw`` is an int for function keys and the typed character (a str)
        for regular input, so multi-byte UTF-8 characters (e.g. Chinese) are
        returned whole instead of as individual bytes.
        """
        try:
            wch = stdscr.get_wch()
        except curses.error:
            return -1, None
        if isinstance(wch, int):
            return wch, wch
        return ord(wch), wch

    def run(self, stdscr):
        """Main loop."""
        # Setup curses
        curses.curs_set(0)
        stdscr.keypad(True)
        curses.start_color()

        # Apply initial theme
        self._apply_theme(stdscr)

        show_help = False

        try:
            while True:
                stdscr.clear()
                height, width = stdscr.getmaxyx()
                self.height, self.width = height, width

                if not self.chapters:
                    stdscr.addstr(0, 0, "No chapters found in this EPUB file.")
                    stdscr.addstr(2, 0, "Press q to quit.")
                    stdscr.refresh()
                    key, _ = self._read_key(stdscr)
                    if key == ord("q"):
                        break
                    continue

                if show_help:
                    self._draw_content(stdscr, height, width)
                    self._draw_help(stdscr, height, width)
                elif self.show_bookshelf:
                    self._draw_bookshelf(stdscr, height, width)
                elif self.show_toc:
                    self._draw_toc(stdscr, height, width)
                elif self.show_search_results:
                    self._draw_search_results(stdscr, height, width)
                else:
                    self._draw_content(stdscr, height, width)
                    self._draw_progress_bar(stdscr, height, width)
                    self._draw_chapter_bar(stdscr, height, width)
                    self._draw_end_marker(stdscr, height, width)
                    self._draw_start_marker(stdscr, height, width)

                if self.show_status_bar and not self.searching:
                    self._draw_status_bar(stdscr, height, width)
                if self.searching:
                    self._draw_search_prompt(stdscr, height, width)
                stdscr.refresh()

                # Handle input
                key, raw_key = self._read_key(stdscr)

                if show_help:
                    show_help = False
                    continue

                if self.show_bookshelf:
                    # Bookshelf navigation
                    if key in (ord("q"), 27, 9):  # q/Esc/Tab: close
                        self.show_bookshelf = False
                    elif key in (curses.KEY_UP, ord("k")):
                        self.shelf_selection = max(0, self.shelf_selection - 1)
                    elif key in (curses.KEY_DOWN, ord("j")):
                        self.shelf_selection = min(len(self.history) - 1, self.shelf_selection + 1)
                    elif key in (curses.KEY_ENTER, 10, 13):  # Enter: open
                        if 0 <= self.shelf_selection < len(self.history):
                            path = self.history[self.shelf_selection]["path"]
                            self.show_bookshelf = False
                            self._open_book(path)
                elif self.show_toc:
                    # TOC navigation
                    if key in (ord("q"), 27):  # q or Escape
                        self.show_toc = False
                        self.toc_input = ""
                    elif key in (curses.KEY_UP, ord("k")):
                        self.toc_selection = max(0, self.toc_selection - 1)
                        self.toc_input = ""
                    elif key in (curses.KEY_DOWN, ord("j")):
                        self.toc_selection = min(len(self.chapters) - 1, self.toc_selection + 1)
                        self.toc_input = ""
                    elif key in (curses.KEY_ENTER, 10, 13):  # Enter
                        if self.toc_input:
                            # Jump to typed chapter number
                            try:
                                target = int(self.toc_input) - 1
                                if 0 <= target < len(self.chapters):
                                    self.current_chapter = target
                                    self.scroll_offset = 0
                            except ValueError:
                                pass
                            self.toc_input = ""
                        else:
                            # Jump to selected chapter
                            self.current_chapter = self.toc_selection
                            self.scroll_offset = 0
                        self.show_toc = False
                    elif key == 9:  # Tab - return to reading without jumping
                        self.show_toc = False
                        self.toc_input = ""
                    elif key in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
                        self.toc_input = self.toc_input[:-1]
                    elif ord("0") <= key <= ord("9"):
                        self.toc_input += chr(key)
                elif self.show_search_results:
                    # Search results navigation
                    if key in (ord("q"), 27, 9):  # q/Esc/Tab: close
                        self.show_search_results = False
                    elif key == ord("/"):  # start a new search
                        self.show_search_results = False
                        self.searching = True
                        self.search_input = ""
                    elif key in (curses.KEY_UP, ord("k")):
                        self.search_selection = max(0, self.search_selection - 1)
                    elif key in (curses.KEY_DOWN, ord("j")):
                        self.search_selection = min(len(self.search_results) - 1, self.search_selection + 1)
                    elif key in (curses.KEY_ENTER, 10, 13):  # Enter: jump
                        self._jump_to_result()
                elif self.searching:
                    # Search prompt input
                    if key in (curses.KEY_ENTER, 10, 13):
                        self._run_search()
                    elif key == 27:  # Escape: cancel
                        self.searching = False
                        self.search_input = ""
                    elif key == 9:  # Tab: cancel
                        self.searching = False
                        self.search_input = ""
                    elif key in (curses.KEY_BACKSPACE, 127, 8):
                        self.search_input = self.search_input[:-1]
                    elif isinstance(raw_key, str) and raw_key.isprintable():
                        # Append the whole character, including CJK/emoji.
                        self.search_input += raw_key
                else:
                    # Content navigation
                    raw_lines = self._get_lines(self.current_chapter)
                    visible_height = height - 1 if self.show_status_bar else height

                    # Calculate display lines for accurate max_scroll
                    text_width = self._text_width(width)
                    display_lines = []
                    for line in raw_lines:
                        if not line:
                            display_lines.append("")
                        else:
                            display_lines.extend(self._wrap_line(line, text_width))
                    max_scroll = max(0, len(display_lines) - visible_height)

                    if key == ord("q"):
                        self._save_current_progress()
                        break
                    elif key == ord("/"):
                        self.searching = True
                        self.search_input = ""
                    elif key == 9:  # Tab
                        self.show_toc = True
                        self.toc_selection = self.current_chapter
                    elif key == ord("?"):
                        show_help = True
                    elif key == ord("s"):
                        self.show_status_bar = not self.show_status_bar
                        save_settings({"show_status_bar": self.show_status_bar})
                    elif key == ord("b"):
                        self.show_progress_bar = not self.show_progress_bar
                        save_settings({"show_progress_bar": self.show_progress_bar})
                        self.message = "Progress bars on" if self.show_progress_bar else "Progress bars off"
                    elif key == ord("H"):
                        self.history = list_history()
                        self.shelf_selection = 0
                        if self.history:
                            self.show_bookshelf = True
                        else:
                            self.message = "No reading history yet"
                    elif key == ord("c"):
                        self.current_theme = (self.current_theme + 1) % len(THEMES)
                        self._apply_theme(stdscr)
                    elif key == ord("n"):
                        self._next_chapter()
                    elif key == ord("p"):
                        self._prev_chapter()
                    elif key in (ord("j"), curses.KEY_DOWN):
                        if self.scroll_offset >= max_scroll:
                            # At end of chapter, go to next
                            self._next_chapter()
                        else:
                            self.scroll_offset = min(max_scroll, self.scroll_offset + 1)
                    elif key in (ord("k"), curses.KEY_UP):
                        if self.scroll_offset <= 0:
                            # At start of chapter, go to previous end
                            self._prev_chapter_end()
                        else:
                            self.scroll_offset = max(0, self.scroll_offset - 1)
                    elif key in (curses.KEY_NPAGE, ord(" ")):  # Page down
                        if self.scroll_offset >= max_scroll:
                            # At end of chapter, go to next
                            self._next_chapter()
                        else:
                            new_offset = self.scroll_offset + visible_height - 2
                            if new_offset >= max_scroll:
                                self.scroll_offset = max_scroll
                            else:
                                self.scroll_offset = new_offset
                    elif key == curses.KEY_PPAGE:  # Page up
                        if self.scroll_offset <= 0:
                            # At start of chapter, go to previous end
                            self._prev_chapter_end()
                        else:
                            self.scroll_offset = max(0, self.scroll_offset - visible_height + 2)
                    elif key in (ord("h"), curses.KEY_LEFT):
                        if self.scroll_offset <= 0:
                            self._prev_chapter_end()
                        else:
                            self.scroll_offset = max(0, self.scroll_offset - visible_height + 2)
                    elif key in (ord("l"), curses.KEY_RIGHT):
                        if self.scroll_offset >= max_scroll:
                            self._next_chapter()
                        else:
                            new_offset = self.scroll_offset + visible_height - 2
                            if new_offset >= max_scroll:
                                self.scroll_offset = max_scroll
                            else:
                                self.scroll_offset = new_offset
                    elif key == ord("g"):
                        self.scroll_offset = 0
                    elif key == ord("G"):
                        self.scroll_offset = max_scroll

                    # Auto-save progress on navigation
                    if key in (ord("j"), ord("k"), curses.KEY_DOWN, curses.KEY_UP,
                               curses.KEY_NPAGE, curses.KEY_PPAGE, ord(" ")):
                        self._save_current_progress()
        finally:
            # Save progress on exit
            self._save_current_progress()
