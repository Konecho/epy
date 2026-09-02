"""Terminal UI for EPUB reader."""

import curses
import unicodedata
from pathlib import Path

from .parser import parse_epub
from .progress import get_book_id, load_progress, save_progress, load_settings, save_settings

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
        self.at_end = False  # Whether we're at the end of current chapter
        self.at_start = False  # Whether we're at the start of current chapter

        # Load settings
        settings = load_settings()
        self.show_status_bar = settings.get("show_status_bar", True)

        self._load_book()
        self._restore_progress()

    def _load_book(self):
        """Load and parse the EPUB file."""
        self.book_title, self.chapters = parse_epub(self.filepath)

    def _restore_progress(self):
        """Restore reading progress from saved state."""
        progress = load_progress(self.book_id)
        if progress:
            chapter = progress.get("chapter", 0)
            scroll = progress.get("scroll", 0)
            if 0 <= chapter < len(self.chapters):
                self.current_chapter = chapter
                self.scroll_offset = scroll
                self.message = f"Restored: Chapter {chapter + 1}"

    def _save_current_progress(self):
        """Save current reading progress."""
        save_progress(self.book_id, self.current_chapter, self.scroll_offset)

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
            stdscr.addstr(height - 1, 0, status[:width - 1].ljust(width))
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
        """Draw START marker when at start of chapter."""
        if self.at_start:
            try:
                stdscr.attron(curses.A_BOLD)
                stdscr.addstr(0, width // 2 - 4, " [START] ")
                stdscr.attroff(curses.A_BOLD)
            except curses.error:
                pass

    def _draw_help(self, stdscr, height: int, width: int):
        """Draw help overlay."""
        help_lines = [
            "EPUB Reader - Keybindings",
            "",
            "  h / ←    Page up",
            "  l / →    Page down",
            "  j / ↓    Scroll down",
            "  k / ↑    Scroll up",
            "  Tab      Toggle table of contents",
            "  s        Toggle status bar",
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
        visible_height = height - 3
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
                if y >= height - 1 or idx >= len(self.chapters):
                    break

                num = f"{idx + 1:>3}."
                title = self.chapters[idx][0]
                # Highlight selection
                prefix = ">> " if idx == self.toc_selection else "   "
                is_current = idx == self.current_chapter
                marker = " *" if is_current else "  "

                line = f"{prefix}{num} {title}{marker}"
                line = line[:width - 1].ljust(width)

                if idx == self.toc_selection:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, 0, line)
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, 0, line)
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

        # Pre-wrap all lines and build display lines
        display_lines = []
        for line in raw_lines:
            if not line:
                display_lines.append("")
            else:
                display_lines.extend(self._wrap_line(line, width))

        # Ensure scroll_offset is valid - allow scrolling until last line is visible
        max_offset = max(0, len(display_lines) - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
        self.max_scroll = max_offset

        # Check if at start or end
        self.at_start = self.scroll_offset == 0
        self.at_end = self.scroll_offset >= max_offset

        for i in range(visible_height):
            line_idx = self.scroll_offset + i
            if line_idx >= len(display_lines):
                break

            line = display_lines[line_idx]
            try:
                stdscr.addstr(i, 0, line[:width], curses.color_pair(1))
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

    def _prev_chapter_end(self):
        """Switch to previous chapter and go to end."""
        if self.current_chapter > 0:
            self.current_chapter -= 1
            # Set scroll to a large value, it will be clamped in _draw_content
            self.scroll_offset = 999999
            self.message = f"Chapter {self.current_chapter + 1}"
            return True
        return False

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

                if not self.chapters:
                    stdscr.addstr(0, 0, "No chapters found in this EPUB file.")
                    stdscr.addstr(2, 0, "Press q to quit.")
                    stdscr.refresh()
                    key = stdscr.getch()
                    if key == ord("q"):
                        break
                    continue

                if show_help:
                    self._draw_content(stdscr, height, width)
                    self._draw_help(stdscr, height, width)
                elif self.show_toc:
                    self._draw_toc(stdscr, height, width)
                else:
                    self._draw_content(stdscr, height, width)
                    self._draw_end_marker(stdscr, height, width)
                    self._draw_start_marker(stdscr, height, width)

                if self.show_status_bar:
                    self._draw_status_bar(stdscr, height, width)
                stdscr.refresh()

                # Handle input
                key = stdscr.getch()

                if show_help:
                    show_help = False
                    continue

                if self.show_toc:
                    # TOC navigation
                    if key in (ord("q"), 27):  # q or Escape
                        self.show_toc = False
                    elif key in (curses.KEY_UP, ord("k")):
                        self.toc_selection = max(0, self.toc_selection - 1)
                    elif key in (curses.KEY_DOWN, ord("j")):
                        self.toc_selection = min(len(self.chapters) - 1, self.toc_selection + 1)
                    elif key in (curses.KEY_ENTER, 10, 13):  # Enter
                        self.current_chapter = self.toc_selection
                        self.scroll_offset = 0
                        self.show_toc = False
                    elif key == 9:  # Tab
                        self.current_chapter = self.toc_selection
                        self.scroll_offset = 0
                        self.show_toc = False
                else:
                    # Content navigation
                    raw_lines = self._get_lines(self.current_chapter)
                    visible_height = height - 1 if self.show_status_bar else height

                    # Calculate display lines for accurate max_scroll
                    display_lines = []
                    for line in raw_lines:
                        if not line:
                            display_lines.append("")
                        else:
                            display_lines.extend(self._wrap_line(line, width))
                    max_scroll = max(0, len(display_lines) - visible_height)

                    if key == ord("q"):
                        self._save_current_progress()
                        break
                    elif key == 9:  # Tab
                        self.show_toc = True
                        self.toc_selection = self.current_chapter
                    elif key == ord("?"):
                        show_help = True
                    elif key == ord("s"):
                        self.show_status_bar = not self.show_status_bar
                        save_settings({"show_status_bar": self.show_status_bar})
                    elif key == ord("c"):
                        self.current_theme = (self.current_theme + 1) % len(THEMES)
                        self._apply_theme(stdscr)
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
