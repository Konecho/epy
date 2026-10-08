# epy - Terminal EPUB Reader

A simple terminal EPUB reader with vim-like keybindings, built with Python and curses.

## Features

- Read EPUB files in the terminal
- Vim-like navigation (hjkl)
- Table of contents (Tab)
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
| `s` | Toggle status bar |
| `b` | Toggle progress bars (book-wide bar under the last line + chapter bar in the last column) |
| `c` | Cycle color theme |
| `?` | Show help |
| `q` | Quit |

### Table of Contents Navigation

When the table of contents is open:

| Key | Action |
|-----|--------|
| `j` / `↓` | Next chapter |
| `k` / `↑` | Previous chapter |
| `Enter` | Jump to selected chapter (or typed number) |
| `Tab` / `Esc` / `q` | Close TOC and return to reading |

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