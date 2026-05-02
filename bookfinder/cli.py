"""Command-line interface using Click + Rich."""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from bookfinder.adapters.registry import register_generic
from bookfinder.config import load_config
from bookfinder.db.database import PriceDatabase
from bookfinder.models import BookQuery, BookResult
from bookfinder.search import search_all_with_report

console = Console()


def _setup_custom_sites() -> None:
    """Load and register custom sites from user config."""
    config = load_config()
    for site in config.custom_sites:
        register_generic(site.name, site.base_url, site.search_url_template)


@click.group()
def main():
    """BookPriceFinder — find the cheapest books across multiple sites."""
    _setup_custom_sites()


@main.command()
@click.argument("query")
@click.option("--isbn", default="", help="Search by ISBN instead of title.")
@click.option("--max-results", "-n", default=None, type=int, help="Max results per source.")
@click.option("--sources", default="", help="Comma-separated sources (e.g. 'AbeBooks,ThriftBooks').")
@click.option("--min-price", type=float, default=None, help="Minimum total price.")
@click.option("--max-price", type=float, default=None, help="Maximum total price.")
@click.option("--offline", is_flag=True, help="Use cached results from database.")
@click.option("--no-save", is_flag=True, help="Don't save results to history.")
def search(
    query: str,
    isbn: str,
    max_results: Optional[int],
    sources: str,
    min_price: Optional[float],
    max_price: Optional[float],
    offline: bool,
    no_save: bool,
):
    """Search for a book across all sources."""
    if max_results is None:
        max_results = load_config().max_results

    book_query = BookQuery(query=query, isbn=isbn, max_results=max_results)

    adapters = None
    if sources:
        from bookfinder.adapters.registry import get_all_adapters
        wanted = {s.strip().lower() for s in sources.split(",") if s.strip()}
        all_adapters = get_all_adapters()
        adapters = [a for a in all_adapters if a.name.lower() in wanted]
        
    if offline:
        with PriceDatabase() as db:
            results = db.get_price_history(isbn=isbn, title=query, limit=max_results)
    else:
        with console.status("Searching..."):
            with PriceDatabase() as db:
                # Use db logging for health
                report = asyncio.run(search_all_with_report(book_query, adapters=adapters, health_logger=db.log_scraper_health))
                results = report.results

    # Filters
    if min_price is not None:
        results = [r for r in results if r.total_price >= min_price]
    if max_price is not None:
        results = [r for r in results if r.total_price <= max_price]

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Process results (save and check deals)
    if not offline and not no_save:
        with PriceDatabase() as db:
            db.save_results(results)
            deals = db.check_wishlist_deals(results)
            for entry, res in deals:
                console.print(f"[bold green]DEAL![/bold green] '{res.title}' for ${res.total_price:.2f} (Wishlist limit: ${entry.max_price:.2f})")

    # Output table
    table = Table(title=f"Results: {query}", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Author", style="dim")
    table.add_column("Price", style="green", justify="right")
    table.add_column("Condition", style="yellow")
    table.add_column("URL", style="blue", max_width=50)

    for r in results:
        price_str = f"${r.total_price:.2f}" if r.price > 0 else "Free/Lend"
        table.add_row(r.source, r.title, r.author, price_str, r.condition.value, r.url)

    console.print(table)


@main.command()
def sources():
    """List and check availability of all sources."""
    from bookfinder.adapters.registry import get_all_adapters
    adapters = get_all_adapters()

    async def _check():
        return await asyncio.gather(*[a.is_available() for a in adapters])

    availability = asyncio.run(_check())
    table = Table(title="Book Sources")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Online", style="green")

    for a, online in zip(adapters, availability, strict=False):
        table.add_row(a.name, a.base_url, "yes" if online else "no")
    console.print(table)


@main.command()
@click.option("--output", "-o", "path", required=True, type=click.Path(dir_okay=False))
@click.option("--format", type=click.Choice(["csv", "json"]), default="csv")
@click.option("--query", default="")
def export(path: str, format: str, query: str):
    """Export history to CSV or JSON."""
    with PriceDatabase() as db:
        rows = db.get_price_history(title=query, limit=1000)

    if not rows:
        console.print("[yellow]No data to export.[/yellow]")
        return

    if format == "csv":
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            # Pydantic models to dict for csv
            data = [r.model_dump() for r in rows]
            # Flatten condition enum
            for d in data:
                d["condition"] = d["condition"]
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    else:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode='json') for r in rows], f, indent=2)

    console.print(f"[green]Exported {len(rows)} items to {path}[/green]")


@main.command()
@click.option("--force", is_flag=True)
def init(force: bool):
    """Initialize default config."""
    from bookfinder.config import write_default_config
    path = write_default_config(force=force)
    console.print(f"[green]Config ready: {path}[/green]")


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=int)
@click.option("--reload", is_flag=True)
def web(host: str, port: int, reload: bool):
    """Start the Web UI."""
    try:
        import uvicorn
        uvicorn.run("bookfinder.web.main:app", host=host, port=port, reload=reload)
    except ImportError:
        console.print("[red]Install 'web' extras: pip install bookpricefinder[web][/red]")


@main.command()
@click.argument("title")
@click.option("--author", "-a", default="")
@click.option("--isbn", default="")
@click.option("--max-price", "-p", type=float)
def wishlist_add(title: str, author: str, isbn: str, max_price: Optional[float]):
    """Track a book."""
    with PriceDatabase() as db:
        db.add_to_wishlist(title, author, isbn, max_price)
    console.print(f"[green]Tracking '{title}'[/green]")


@main.command()
def wishlist():
    """List tracked books."""
    with PriceDatabase() as db:
        entries = db.get_wishlist()
    if not entries:
        console.print("[yellow]Wishlist is empty.[/yellow]")
        return
    table = Table(title="Wishlist")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Author")
    table.add_column("Limit")
    for e in entries:
        limit = f"${e.max_price:.2f}" if e.max_price else "-"
        table.add_row(str(e.id), e.title, e.author, limit)
    console.print(table)


if __name__ == "__main__":
    main()
