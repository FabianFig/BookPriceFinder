"""SQLite database for price history tracking and wishlists."""

import sqlite3
from pathlib import Path

from bookfinder.models import BookResult

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "bookfinder" / "prices.db"

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

    # ── Price History ──

    def save_results(self, results: list[BookResult]) -> int:
        """Save search results to price history. Returns number of rows inserted."""
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
    ) -> list[dict]:
        """Get price history for a book by ISBN or title."""
        if isbn:
            cursor = self._conn.execute(
                """SELECT * FROM price_history
                   WHERE isbn = ? ORDER BY searched_at DESC LIMIT ?""",
                (isbn, limit),
            )
        elif title:
            cursor = self._conn.execute(
                """SELECT * FROM price_history
                   WHERE title LIKE ? ORDER BY searched_at DESC LIMIT ?""",
                (f"%{title}%", limit),
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM price_history ORDER BY searched_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_results(
        self, isbn: str = "", title: str = "", limit: int = 50
    ) -> list[dict]:
        """Get recent results for a query (offline mode)."""
        if isbn:
            cursor = self._conn.execute(
                """SELECT * FROM price_history
                   WHERE isbn = ? ORDER BY searched_at DESC LIMIT ?""",
                (isbn, limit),
            )
        elif title:
            cursor = self._conn.execute(
                """SELECT * FROM price_history
                   WHERE title LIKE ? ORDER BY searched_at DESC LIMIT ?""",
                (f"%{title}%", limit),
            )
        else:
            cursor = self._conn.execute(
                "SELECT * FROM price_history ORDER BY searched_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_lowest_price(self, isbn: str = "", title: str = "") -> dict | None:
        """Get the lowest price ever recorded for a book."""
        if isbn:
            where, param = "isbn = ?", isbn
        elif title:
            where, param = "title LIKE ?", f"%{title}%"
        else:
            return None

        cursor = self._conn.execute(
            f"""SELECT *, (price + COALESCE(shipping, 0)) AS total
                FROM price_history
                WHERE {where} AND price > 0
                ORDER BY total ASC LIMIT 1""",
            (param,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ── Wishlist ──

    def add_to_wishlist(
        self, title: str, author: str = "", isbn: str = "", max_price: float | None = None
    ) -> int:
        """Add a book to the wishlist. Returns the wishlist entry ID."""
        cursor = self._conn.execute(
            """INSERT INTO wishlist (title, author, isbn, max_price)
               VALUES (?, ?, ?, ?)""",
            (title, author, isbn, max_price),
        )
        self._conn.commit()
        return cursor.lastrowid

    def remove_from_wishlist(self, wishlist_id: int) -> bool:
        """Remove a book from the wishlist by ID."""
        cursor = self._conn.execute(
            "DELETE FROM wishlist WHERE id = ?", (wishlist_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get_wishlist(self) -> list[dict]:
        """Get all wishlist entries."""
        cursor = self._conn.execute(
            "SELECT * FROM wishlist ORDER BY added_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def check_wishlist_deals(self, results: list[BookResult]) -> list[tuple[dict, BookResult]]:
        """Check if any search results match wishlist items under max_price.

        Returns list of (wishlist_entry, matching_result) tuples.
        """
        wishlist = self.get_wishlist()
        deals: list[tuple[dict, BookResult]] = []

        for entry in wishlist:
            max_price = entry.get("max_price")
            if max_price is None:
                continue

            for result in results:
                if result.price <= 0:
                    continue

                # Match by ISBN or fuzzy title match
                isbn_match = entry["isbn"] and entry["isbn"] == result.isbn
                title_match = entry["title"].lower() in result.title.lower()

                if (isbn_match or title_match) and result.total_price <= max_price:
                    deals.append((entry, result))

        return deals

    # ── Saved Searches ──

    def save_search(self, name: str, params: dict) -> int:
        """Save a search preset. Returns the saved search ID."""
        import json

        cursor = self._conn.execute(
            "INSERT INTO saved_searches (name, params) VALUES (?, ?)",
            (name, json.dumps(params)),
        )
        self._conn.commit()
        return cursor.lastrowid

    def list_saved_searches(self) -> list[dict]:
        """List saved search presets."""
        cursor = self._conn.execute(
            "SELECT id, name, created_at FROM saved_searches ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_saved_search(self, search_id: int) -> dict | None:
        """Get a saved search by ID."""
        cursor = self._conn.execute(
            "SELECT * FROM saved_searches WHERE id = ?",
            (search_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_saved_search(self, search_id: int) -> bool:
        """Delete a saved search by ID."""
        cursor = self._conn.execute(
            "DELETE FROM saved_searches WHERE id = ?",
            (search_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0
