# BookPriceFinder

**GitHub:** https://github.com/FabianFig/BookPriceFinder

Find the best book prices across multiple sites from a simple command-line or web interface. Results are saved to a local SQLite database to track price history, calculate market "Deal Scores", and set wishlist alerts.

## About This Project

Built for casual book buyers who love finding cheap, pre-loved used books. Searches typically take 5-15 seconds depending on how many sources you enable.

**Requirements:** Python 3.10 or higher

## Features

- **Multi-Source Search:** Queries AbeBooks, ThriftBooks, World of Books, and more in parallel.
- **Market Intelligence:** Automatically calculates a "Deal Score" based on historical averages in your database.
- **Price History:** Interactive charts visualize price trends over time.
- **Bulk Import:** Upload a list of ISBNs to your wishlist in one go.
- **Multi-Currency:** Support for USD, GBP, EUR, CAD, AUD, and JPY with offline conversion.
- **Scraper Health:** A dedicated dashboard to monitor which retailers are online.
- **Digital Editions:** Automatically finds free ebooks from Project Gutenberg for public domain titles.

## Quick Start

### 1. Install & Setup

**Linux / macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[web,browser]"
bookfinder init
playwright install chromium
```

**Windows:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web,browser]"
bookfinder init
playwright install chromium
```

### 2. Run the Web UI

```bash
bookfinder web
```

Access the dashboard at **http://127.0.0.1:8000**.

## Supported Sources

- **Retailers:** AbeBooks, ThriftBooks, World of Books, HPB, PangoBooks.
- **Digital/Library:** Open Library, Project Gutenberg.
- **Custom:** Add any site that uses Schema.org structured data via `config.toml`.

## Web UI Features

- **Real-time Search:** App-like experience with dynamic loading states.
- **Price Visualization:** Click "History" on any result to see the price trend chart.
- **Smart Filtering:** Intelligently filters out non-book media (DVDs/CDs) from retailers.
- **Wishlist Manager:** Mass-add books via ISBN file upload or individual entry.
- **System Dashboard:** Monitor scraper success/failure rates at `/status`.

## CLI Usage

### `bookfinder search <query>`
Search for a book. Use `--isbn` for precise matches.

### `bookfinder export`
Export your entire search history to CSV or JSON:
`bookfinder export -o data.json --format json`

### `bookfinder wishlist`
Manage your tracked books and target budgets.

## Configuration

Add custom sites in `~/.config/bookfinder/config.toml`:

```toml
[[sites]]
name = "LocalStore"
base_url = "https://localstore.com"
search_url_template = "https://localstore.com/search?q={query}"
```

## Self-Hosting (Docker)

BPF is ready for home servers/NAS:

```bash
docker-compose up -d
```

## Privacy & Data

All data stays on your machine in a local SQLite database. No tracking, no external accounts, no cloud dependencies.

## License

MIT License - see [LICENSE](LICENSE) file for details.
