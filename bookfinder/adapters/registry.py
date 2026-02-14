"""Adapter registry — central place to manage which sources are active."""

from bookfinder.adapters.base import BaseAdapter
from bookfinder.adapters.generic import GenericAdapter
from bookfinder.adapters.abebooks import AbeBooksAdapter
from bookfinder.adapters.hpb import HPBAdapter
from bookfinder.adapters.openlibrary import OpenLibraryAdapter
from bookfinder.adapters.pangobooks import PangoBooksAdapter
from bookfinder.adapters.thriftbooks import ThriftBooksAdapter
from bookfinder.adapters.worldofbooks import WorldOfBooksAdapter

# Built-in adapters
_BUILTIN_ADAPTERS: list[BaseAdapter] = [
    AbeBooksAdapter(),
    ThriftBooksAdapter(),
    HPBAdapter(),
    PangoBooksAdapter(),
    WorldOfBooksAdapter(),
    OpenLibraryAdapter(),
]

_custom_adapters: list[BaseAdapter] = []


def get_all_adapters() -> list[BaseAdapter]:
    """Return all registered adapters (built-in + custom)."""
    return _BUILTIN_ADAPTERS + _custom_adapters


def register_adapter(adapter: BaseAdapter) -> None:
    """Register a custom adapter at runtime."""
    _custom_adapters.append(adapter)


def register_generic(name: str, base_url: str, search_url_template: str) -> None:
    """Register a generic structured-data adapter."""
    _custom_adapters.append(GenericAdapter(name, base_url, search_url_template))
