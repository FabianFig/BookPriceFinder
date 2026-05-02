"""SQLite database for price history tracking and wishlists."""

import sqlite3
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

from bookfinder.models import (
    BookResult,
    Condition,
    ScraperHealthEntry,
    WishlistEntry,
)

DEFAULT_DB_PATH = Path(user_data_dir("bookfinder")) / "prices.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT,
    title TEXT NOT NULL,
    author TEXT,
    price REAL NOT NULL,
    shipping REAL,
    currency TEXT DEFAULT 'USD',
    condition TEXT,
    source TEXT NOT NULL,
    url TEXT,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_isbn ON price_history(isbn);
CREATE INDEX IF NOT EXISTS idx_price_title ON price_history(title);
CREATE INDEX IF NOT EXISTS idx_price_searched_at ON price_history(searched_at);

CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    isbn TEXT,
    max_price REAL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wishlist_isbn ON wishlist(isbn);

CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    params TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_name ON saved_searches(name);

CREATE TABLE IF NOT EXISTS scraper_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_health_source ON scraper_health(source);
CREATE INDEX IF NOT EXISTS idx_health_searched_at ON scraper_health(searched_at);
"""


class PriceDatabase:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _row_to_book_result(self, row: sqlite3.Row) -> BookResult:
        return BookResult(
            title=row["title"],
            author=row["author"] or "Unknown",
            price=row["price"],
            currency=row["currency"],
            condition=Condition(row["condition"] or "unknown"),
            source=row["source"],
            url=row["url"],
            isbn=row["isbn"] or "",
            shipping=row["shipping"],
            searched_at=row["searched_at"],
        )

    def _row_to_wishlist_entry(self, row: sqlite3.Row) -> WishlistEntry:
        return WishlistEntry(
            id=row["id"],
            title=row["title"],
            author=row["author"] or "",
            isbn=row["isbn"] or "",
            max_price=row["max_price"],
            added_at=row["added_at"],
        )

    # ── Price History ──

    def save_results(self, results: list[BookResult]) -> int:
        """Save search results to price history."""
        rows = [
            (
                r.isbn,
                r.title,
                r.author,
                r.price,
                r.shipping,
                r.currency,
                r.condition.value,
                r.source,
                r.url,
            )
            for r in results
        ]
        self._conn.executemany(
            """INSERT INTO price_history
               (isbn, title, author, price, shipping, currency, condition, source, url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def get_price_history(
        self, isbn: str = "", title: str = "", limit: int = 50
    ) -> list[BookResult]:
        """Get price history for a book by ISBN or title."""
        if isbn:
            cursor = self._conn.execute(
                "SELECT * FROM price_history WHERE isbn = ? ORDER BY searched_at DESC LIMIT ?",
                (isbn, limit),
            )
        elif title:
            search_title = f"%{title.replace(' ', '%')}%"
            cursor = self._conn.execute(
                """SELECT * FROM price_history
                   WHERE title LIKE ? OR author LIKE ? 
                   ORDER BY searched_at DESC LIMIT ?""",
                (search_title, search_title, limit),
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM price_history ORDER BY searched_at DESC LIMIT ?",
                (limit,),
            )
        return [self._row_to_book_result(row) for row in cursor.fetchall()]

    def get_average_price(self, isbn: str = "", title: str = "") -> float | None:
        """Get the average price for a book from history."""
        if isbn:
            where, param = "isbn = ?", isbn
        elif title:
            where, param = "title LIKE ?", f"%{title}%"
        else:
            return None

        row = self._conn.execute(
            f"SELECT AVG(price + COALESCE(shipping, 0)) as avg_price FROM price_history WHERE {where} AND price > 0",
            (param,),
        ).fetchone()
        return row["avg_price"] if row and row["avg_price"] else None

    # ── Wishlist ──

    def add_to_wishlist(
        self, title: str, author: str = "", isbn: str = "", max_price: float | None = None
    ) -> int:
        """Add a book to the wishlist."""
        cursor = self._conn.execute(
            "INSERT INTO wishlist (title, author, isbn, max_price) VALUES (?, ?, ?, ?)",
            (title, author, isbn, max_price),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def remove_from_wishlist(self, wishlist_id: int) -> bool:
        """Remove a book from the wishlist by ID."""
        cursor = self._conn.execute("DELETE FROM wishlist WHERE id = ?", (wishlist_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_wishlist(self) -> list[WishlistEntry]:
        """Get all wishlist entries."""
        cursor = self._conn.execute("SELECT * FROM wishlist ORDER BY added_at DESC")
        return [self._row_to_wishlist_entry(row) for row in cursor.fetchall()]

    def check_wishlist_deals(self, results: list[BookResult]) -> list[tuple[WishlistEntry, BookResult]]:
        """Check if any search results match wishlist items under max_price."""
        wishlist = self.get_wishlist()
        deals = []
        for entry in wishlist:
            if entry.max_price is None:
                continue
            for result in results:
                if result.price <= 0:
                    continue
                isbn_match = entry.isbn and entry.isbn == result.isbn
                title_match = entry.title.lower() in result.title.lower()
                if (isbn_match or title_match) and result.total_price <= entry.max_price:
                    deals.append((entry, result))
        return deals

    # ── Saved Searches ──

    def save_search(self, name: str, params: dict) -> int:
        """Save a search preset."""
        import json
        cursor = self._conn.execute(
            "INSERT INTO saved_searches (name, params) VALUES (?, ?)",
            (name, json.dumps(params)),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def list_saved_searches(self) -> list[dict]:
        """List saved search presets."""
        cursor = self._conn.execute("SELECT id, name, created_at FROM saved_searches ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_saved_search(self, search_id: int) -> Optional[dict]:
        """Get a saved search by ID."""
        cursor = self._conn.execute("SELECT * FROM saved_searches WHERE id = ?", (search_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_saved_search(self, search_id: int) -> bool:
        """Delete a saved search by ID."""
        cursor = self._conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ── Scraper Health ──

    def log_scraper_health(self, source: str, success: bool, error_message: str | None = None) -> None:
        """Log the result of a scraper run."""
        self._conn.execute(
            "INSERT INTO scraper_health (source, success, error_message) VALUES (?, ?, ?)",
            (source, 1 if success else 0, error_message),
        )
        self._conn.commit()

    def get_scraper_health(self, limit_per_source: int = 20) -> list[ScraperHealthEntry]:
        """Get the latest health logs for each source."""
        cursor = self._conn.execute(
            """SELECT * FROM (
                 SELECT *, ROW_NUMBER() OVER (PARTITION BY source ORDER BY searched_at DESC) as rn
                 FROM scraper_health
               ) WHERE rn <= ? ORDER BY source, searched_at DESC""",
            (limit_per_source,),
        )
        return [
            ScraperHealthEntry(
                id=row["id"],
                source=row["source"],
                success=bool(row["success"]),
                error_message=row["error_message"],
                searched_at=row["searched_at"],
            )
            for row in cursor.fetchall()
        ]
