"""Base adapter that all site adapters must implement."""

from abc import ABC, abstractmethod

from bookfinder.models import BookQuery, BookResult


class BaseAdapter(ABC):
    """Interface for a book price source.

    To add a new site, subclass this and implement the two required methods.
    Drop the file into bookfinder/adapters/ and register it in the adapter registry.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this source (e.g. 'ThriftBooks')."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the site."""

    @abstractmethod
    async def search(self, query: BookQuery) -> list[BookResult]:
        """Search for books matching the query and return price results."""

    async def is_available(self) -> bool:
        """Check if the source is reachable. Override for custom health checks."""
        return True
