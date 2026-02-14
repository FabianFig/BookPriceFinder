# BookPriceFinder

**GitHub:** https://github.com/FabianFig/BookPriceFinder

Find the best book prices across multiple sites from a simple command-line interface. Results are saved to a local SQLite database so you can track price history and set wishlist alerts.

## About This Project

This was originally built as a personal tool for home use with AI assistance and hands-on refinement. It worked well enough that a friend wanted to use it, so I'm making it public. Feel free to use it, modify it, or submit improvements.

Built for casual book buyers who love finding cheap, pre-loved used books. Searches typically take 5-10 seconds depending on how many sources you enable.

**Requirements:** Python 3.10 or higher

## Features

- Search multiple sources at once (async + parallel)
- Track price history automatically (SQLite)
- Wishlist with price alerts
- Optional Playwright support for JS-rendered sites
- Add custom sites via a config file (no code required)

## Supported Sources

- AbeBooks
- ThriftBooks
- World of Books
- Open Library (free/lending)
- PangoBooks (requires Playwright)
- Half Price Books (may be blocked by bot protection)

## Quick Start (Recommended for non-tech users)

### Option A: Install with pipx (isolated, best for CLI tools)

1. Install pipx: https://pipx.pypa.io/stable/installation/
2. From the project folder:

```
python -m pip install --user pipx
python -m pipx ensurepath
pipx install .
```

Run a search:

```
bookfinder search "Dune" -n 5
```

Create a default config file:

```
bookfinder init
```

### Option B: Install with venv (standard Python)

**Linux / macOS:**

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
bookfinder search "Dune" -n 5
```

**Windows (PowerShell):**

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
bookfinder search "Dune" -n 5
```

**Windows (Command Prompt):**

```
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e .
bookfinder search "Dune" -n 5
```

## Playwright (for PangoBooks and better JS support)

```
pip install "bookpricefinder[browser]"
playwright install chromium
```

## Minimal Web UI (optional)

```
pip install "bookpricefinder[web]"
bookfinder web
```

Web UI features include pagination, source toggles (with 'All' toggle), saved searches, ISBN-only search mode, light/dark theme, result caching, comparison table, and CSV export.

## Docker (optional)

```
docker build -t bookpricefinder .
docker run --rm -p 8000:8000 bookpricefinder
```

## Configuration

Copy the example file and edit it:

**Linux / macOS:**

```
mkdir -p ~/.config/bookfinder
cp config.example.toml ~/.config/bookfinder/config.toml
```

**Windows (PowerShell):**

```
New-Item -ItemType Directory -Force -Path "$env:APPDATA\bookfinder"
Copy-Item config.example.toml "$env:APPDATA\bookfinder\config.toml"
```

Or use the one-command setup (works on all platforms):

```
bookfinder init
```

You can add custom sites that expose Schema.org JSON-LD (Product/Offer) on their search pages.

Example:

```
[[sites]]
name = "MyBookStore"
base_url = "https://mybookstore.com"
search_url_template = "https://mybookstore.com/search?q={query}"
```

## Commands

### `bookfinder search <query>`

Search for a book across all sources.

| Option | Short | Description |
|--------|-------|-------------|
| `--isbn TEXT` | | Search by ISBN instead of title |
| `--max-results N` | `-n` | Max results per source (defaults to config value) |
| `--sources TEXT` | | Comma-separated list of sources (e.g. `"AbeBooks,ThriftBooks"`) |
| `--min-price N` | | Only show results at or above this total price |
| `--max-price N` | | Only show results at or below this total price |
| `--offline` | | Show cached results from the local database instead of searching live |
| `--no-save` | | Don't save results to price history |

```
bookfinder search "Dune" -n 5
bookfinder search "Dune" --sources "AbeBooks,ThriftBooks"
bookfinder search "Dune" --min-price 5 --max-price 20
bookfinder search "Dune" --offline
```

### `bookfinder sources`

List all registered book sources and whether they're currently reachable.

### `bookfinder export`

Export price history to a CSV file.

| Option | Short | Description |
|--------|-------|-------------|
| `--csv PATH` | | (Required) Output CSV file path |
| `--query TEXT` | | Filter by title |
| `--isbn TEXT` | | Filter by ISBN |
| `--limit N` | `-n` | Max rows to export (default: 200) |

```
bookfinder export --csv results.csv --query "Dune"
```

### `bookfinder wishlist-add <title>`

Add a book to the wishlist. You'll be alerted during searches if a result drops below your max price.

| Option | Short | Description |
|--------|-------|-------------|
| `--author TEXT` | `-a` | Book author |
| `--isbn TEXT` | | Book ISBN |
| `--max-price N` | `-p` | Alert when price drops below this amount |

```
bookfinder wishlist-add "Dune" --max-price 5.00
```

### `bookfinder wishlist`

Show all books on your wishlist.

### `bookfinder wishlist-remove <id>`

Remove a book from the wishlist by its ID (shown in `bookfinder wishlist`).

### `bookfinder history <query>`

Show price history for a book from previous searches.

| Option | Short | Description |
|--------|-------|-------------|
| `--isbn TEXT` | | Filter by ISBN |
| `--limit N` | `-n` | Max history entries (default: 20) |

```
bookfinder history "Dune"
```

### `bookfinder init`

Create a default config file in the user config directory.

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing config file |

### `bookfinder web`

Run the minimal web UI (requires the `web` extra).

| Option | Description |
|--------|-------------|
| `--host TEXT` | Host to bind to (default: `127.0.0.1`) |
| `--port N` | Port to listen on (default: `8000`) |

## Data Storage

Price history and wishlist data are stored locally at:

- **Linux:** `~/.local/share/bookfinder/prices.db`
- **macOS:** `~/Library/Application Support/bookfinder/prices.db`
- **Windows:** `C:\Users\<YourUsername>\AppData\Local\bookfinder\prices.db`

**Privacy:** All data stays on your machine. The tool only scrapes public book listing pages and doesn't send your searches anywhere else.

**Data Freshness:** Searches are live-scraped each time for up-to-date prices. The web UI caches results for 5 minutes to avoid overwhelming book sites.

## Downloads (GitHub Releases)

Tagged releases publish a prebuilt zip file in GitHub Releases. Download the latest zip, unzip it, and run the install steps in this README.

## Notes / Limitations

- I daily-drive Arch Linux, so that's where this gets the most testing. The Windows and macOS instructions should work but I haven't tested them much. If something's off, open an issue and I'll take a look.
- Half Price Books uses strict bot protection and may block headless browsers.
- PangoBooks requires Playwright to render results.

## Troubleshooting

- **`bookfinder` command not found**: Ensure your install method added the CLI to PATH. With pipx, run `pipx ensurepath` and reopen your terminal.
- **PangoBooks empty results**: Install Playwright and Chromium (see Playwright section).
- **HPB empty results or error page**: HPB blocks headless browsers; try again later or exclude it with `--sources`.
- **Permission errors writing config**: Run `bookfinder init --force` after checking directory permissions.

## Contributing

Issues and pull requests welcome! This is a casual project, so don't worry about perfect code, just share what works.

## License

MIT License - see [LICENSE](LICENSE) file for details.
