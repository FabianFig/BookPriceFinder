from dataclasses import dataclass, field
from enum import Enum


class Condition(Enum):
    NEW = "new"
    USED = "used"
    UNKNOWN = "unknown"


@dataclass
class BookResult:
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

    @property
    def total_price(self) -> float:
        return self.price + (self.shipping or 0.0)


@dataclass
class BookQuery:
    """What the user is searching for."""

    query: str
    isbn: str = ""
    max_results: int = 5
