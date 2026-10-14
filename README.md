# epy - Terminal EPUB Reader

A simple terminal EPUB reader with vim-like keybindings, built with Python and curses.

## Features

- Read EPUB files in the terminal
- Vim-like navigation (hjkl)
- Table of contents (Tab)
- Full-text search (`/`) with a TOC-like result list that jumps to the matching line
- Chapter navigation
- Word wrapping
- White background with black text
- Automatic reading progress saving
- Progress persists across sessions (stored in `~/.local/share/epy/`)
- Auto chapter transition: scroll past end/start to switch chapters
- [END]/[START] markers at chapter boundaries

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for package management.

```bash
# Clone the repository
git clone <repo-url>
cd epy

# Install dependencies
uv sync
```

## Usage

```bash
# Run directly with uv
uv run epy <file.epub>

# Or activate the venv first
source .venv/bin/activate
epy <file.epub>

# Open the last book (no arguments)
uv run epy
```

## Keybindings

| Key | Action |
|-----|--------|
| `h` / `←` | Page up |
| `l` / `→` | Page down |
| `j` / `↓` | Scroll down one line |
| `k` / `↑` | Scroll up one line |
| `Space` / `Page Down` | Page down |
| `Page Up` | Page up |
| `g` | Go to top |
| `G` | Go to bottom |
| `Tab` | Toggle table of contents |
| `/` | Search the book |
| `s` | Toggle status bar |
| `b` | Toggle progress bars (book-wide bar under the last line + chapter bar in the last column) |
| `H` | Open bookshelf (reading history) |
| `c` | Cycle color theme |
| `?` | Show help |
| `q` | Quit |

### Search

Press `/` to search the whole book. Type a query and press `Enter`; the
matches open in a TOC-like list showing the excerpt and the chapter number,
with the matched word reverse-highlighted. Selecting an entry jumps straight
to the matching line. Queries may contain non-ASCII text such as Chinese (the
terminal locale must be UTF-8).

| Key | Action |
|-----|--------|
| `/` | Open the search prompt |
| `Enter` | Run the search / jump to the selected result |
| `j` / `↓` | Next result |
| `k` / `↑` | Previous result |
| `/` | Start a new search (in the result list) |
| `Esc` / `Tab` / `q` | Close the search prompt or result list |

### Table of Contents Navigation

When the table of contents is open:

| Key | Action |
|-----|--------|
| `j` / `↓` | Next chapter |
| `k` / `↑` | Previous chapter |
| `Enter` | Jump to selected chapter (or typed number) |
| `Tab` / `Esc` / `q` | Close TOC and return to reading |

### Bookshelf

Press `H` to open the bookshelf: a list of previously opened books, most
recently read first, with the whole-book reading percentage, the last
chapter, and how long ago it was opened. Books opened before this feature
existed show `-` until they are saved again.

| Key | Action |
|-----|--------|
| `j` / `↓` | Next book |
| `k` / `↑` | Previous book |
| `Enter` | Open the selected book |
| `Tab` / `Esc` / `q` | Close the bookshelf |

## Project Structure

```
src/epy/
├── __init__.py    # Entry point
├── parser.py      # EPUB parsing
├── progress.py    # Reading progress persistence
└── reader.py      # Terminal UI
```

## Requirements

- Python 3.13+
- ebooklib
- beautifulsoup4

## License

MIT