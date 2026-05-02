from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class Condition(Enum):
    NEW = "new"
    USED = "used"
    UNKNOWN = "unknown"


class BookResult(BaseModel):
    """A single price result from a source."""

    title: str
    author: str
    price: float
    currency: str
    condition: Condition
    source: str
    url: str
    isbn: str = ""
    shipping: float | None = None
    cover_url: str | None = None
    deal_score: float | None = None
    searched_at: datetime | None = None

    @property
    def total_price(self) -> float:
        return self.price + (self.shipping or 0.0)


class BookQuery(BaseModel):
    """What the user is searching for."""

    query: str
    isbn: str = ""
    max_results: int = 5


class SearchReport(BaseModel):
    """Results plus per-source status info."""

    results: list[BookResult] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    elapsed: float = 0.0


class WishlistEntry(BaseModel):
    """An item tracked in the wishlist."""

    id: int
    title: str
    author: str = ""
    isbn: str = ""
    max_price: float | None = None
    added_at: datetime


class ScraperHealthEntry(BaseModel):
    """A health log entry for a scraper."""

    id: int
    source: str
    success: bool
    error_message: str | None = None
    searched_at: datetime
