"""Command-line interface using Click + Rich."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

from bookfinder.adapters.registry import register_generic
from bookfinder.config import load_config
from bookfinder.db.database import PriceDatabase
from bookfinder.models import BookQuery, BookResult, Condition
from bookfinder.search import search_all

console = Console()


def _setup_custom_sites() -> None:
    """Load custom sites from user config and register them."""
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
@click.option(
    "--max-results",
    "-n",
    default=None,
    type=int,
    help="Max results per source (defaults to config).",
)
@click.option(
    "--sources",
    default="",
    help="Comma-separated list of sources to use (e.g. 'AbeBooks,ThriftBooks').",
)
@click.option("--min-price", type=float, default=None, help="Minimum total price filter.")
@click.option("--max-price", type=float, default=None, help="Maximum total price filter.")
@click.option("--offline", is_flag=True, help="Use cached results from the database.")
@click.option("--no-save", is_flag=True, help="Don't save results to price history.")
def search(
    query: str,
    isbn: str,
    max_results: int | None,
    sources: str,
    min_price: float | None,
    max_price: float | None,
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
        missing = wanted - {a.name.lower() for a in adapters}
        if missing:
            console.print(
                f"[yellow]Unknown sources ignored:[/yellow] {', '.join(sorted(missing))}"
            )
        if not adapters:
            console.print("[red]No valid sources selected.[/red]")
            return

    if offline:
        with PriceDatabase() as db:
            cached = db.get_recent_results(isbn=isbn, title=query, limit=max_results * 10)
        results = [
            BookResult(
                title=row["title"],
                author=row["author"] or "Unknown",
                price=row["price"],
                shipping=row["shipping"],
                currency=row.get("currency") or "USD",
                condition=Condition(row["condition"]) if row.get("condition") else Condition.UNKNOWN,
                source=row["source"],
                url=row.get("url") or "",
                isbn=row.get("isbn") or "",
            )
            for row in cached
        ]
    else:
        with console.status("Searching..."):
            results = asyncio.run(search_all(book_query, adapters=adapters))

    if min_price is not None or max_price is not None:
        def _in_range(r: BookResult) -> bool:
            total = r.total_price
            if min_price is not None and total < min_price:
                return False
            if max_price is not None and total > max_price:
                return False
            return True

        results = [r for r in results if _in_range(r)]

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Save to price history
    if not no_save and not offline:
        with PriceDatabase() as db:
            saved = db.save_results(results)
            # Check for wishlist deals
            deals = db.check_wishlist_deals(results)
            for entry, result in deals:
                console.print(
                    f"[bold green]DEAL![/bold green] "
                    f"'{result.title}' at {result.source} for "
                    f"${result.total_price:.2f} "
                    f"(wishlist max: ${entry['max_price']:.2f})"
                )

    if results:
        best_deals = [r for r in results if r.price > 0][:3]
        if best_deals:
            console.print("[bold]Best deals:[/bold]")
            for r in best_deals:
                console.print(
                    f"- {r.title} ({r.source}) ${r.total_price:.2f}"
                )

    table = Table(title=f"Results for: {query}", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Author", style="dim")
    table.add_column("Price", style="green", justify="right")
    table.add_column("Condition", style="yellow")
    table.add_column("URL", style="blue", max_width=50)

    for r in results:
        price_str = f"${r.total_price:.2f}" if r.price > 0 else "Free/Lend"
        table.add_row(
            r.source,
            r.title,
            r.author,
            price_str,
            r.condition.value,
            r.url,
        )

    console.print(table)


@main.command()
def sources():
    """List all registered book sources."""
    from bookfinder.adapters.registry import get_all_adapters

    adapters = get_all_adapters()

    async def _check_availability():
        checks = [adapter.is_available() for adapter in adapters]
        return await asyncio.gather(*checks)

    availability = asyncio.run(_check_availability())

    table = Table(title="Registered Sources")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Available", style="green")

    for adapter, available in zip(adapters, availability, strict=False):
        table.add_row(adapter.name, adapter.base_url, "yes" if available else "no")

    console.print(table)


@main.command()
@click.option("--csv", "csv_path", required=True, type=click.Path(dir_okay=False))
@click.option("--query", default="", help="Filter by title contains query.")
@click.option("--isbn", default="", help="Filter by ISBN.")
@click.option("--limit", "-n", default=200, help="Max rows to export.")
def export(csv_path: str, query: str, isbn: str, limit: int):
    """Export price history to CSV."""
    import csv

    with PriceDatabase() as db:
        rows = db.get_price_history(isbn=isbn, title=query, limit=limit)

    if not rows:
        console.print("[yellow]No data to export.[/yellow]")
        return

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"[green]Exported[/green] {len(rows)} rows to {csv_path}")


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
def init(force: bool):
    """Create a default config file in the user config directory."""
    from bookfinder.config import write_default_config

    path = write_default_config(force=force)
    console.print(f"[green]Config written to:[/green] {path}")


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind the web UI.")
@click.option("--port", default=8000, type=int, help="Port for the web UI.")
def web(host: str, port: int):
    """Run the minimal web UI (requires the web extra)."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Web UI requires extra dependencies.[/red] "
            "Install with: pip install bookpricefinder[web]"
        )
        return

    uvicorn.run("bookfinder.web:app", host=host, port=port, reload=False)


@main.command()
@click.argument("title")
@click.option("--author", "-a", default="", help="Book author.")
@click.option("--isbn", default="", help="Book ISBN.")
@click.option("--max-price", "-p", type=float, default=None, help="Alert when price drops below.")
def wishlist_add(title: str, author: str, isbn: str, max_price: float | None):
    """Add a book to the wishlist."""
    with PriceDatabase() as db:
        entry_id = db.add_to_wishlist(title, author, isbn, max_price)
    price_note = f" (alert below ${max_price:.2f})" if max_price else ""
    console.print(f"[green]Added '{title}' to wishlist (#{entry_id}){price_note}[/green]")


@main.command()
@click.argument("wishlist_id", type=int)
def wishlist_remove(wishlist_id: int):
    """Remove a book from the wishlist by ID."""
    with PriceDatabase() as db:
        if db.remove_from_wishlist(wishlist_id):
            console.print(f"[green]Removed wishlist entry #{wishlist_id}[/green]")
        else:
            console.print(f"[red]Wishlist entry #{wishlist_id} not found[/red]")


@main.command()
def wishlist():
    """Show the current wishlist."""
    with PriceDatabase() as db:
        entries = db.get_wishlist()

    if not entries:
        console.print("[yellow]Wishlist is empty.[/yellow]")
        return

    table = Table(title="Wishlist")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="white")
    table.add_column("Author", style="dim")
    table.add_column("ISBN", style="dim")
    table.add_column("Max Price", style="green", justify="right")

    for e in entries:
        max_p = f"${e['max_price']:.2f}" if e["max_price"] else "-"
        table.add_row(str(e["id"]), e["title"], e["author"] or "-", e["isbn"] or "-", max_p)

    console.print(table)


@main.command()
@click.argument("query")
@click.option("--isbn", default="", help="Filter by ISBN.")
@click.option("--limit", "-n", default=20, help="Max history entries.")
def history(query: str, isbn: str, limit: int):
    """Show price history for a book."""
    with PriceDatabase() as db:
        if isbn:
            entries = db.get_price_history(isbn=isbn, limit=limit)
        else:
            entries = db.get_price_history(title=query, limit=limit)

        lowest = db.get_lowest_price(isbn=isbn, title=query if not isbn else "")

    if not entries:
        console.print("[yellow]No price history found.[/yellow]")
        return

    if lowest:
        console.print(
            f"[bold]Lowest ever:[/bold] ${lowest['total']:.2f} "
            f"at {lowest['source']} on {lowest['searched_at']}"
        )

    table = Table(title=f"Price History: {query}")
    table.add_column("Date", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Price", style="green", justify="right")
    table.add_column("Condition", style="yellow")

    for e in entries:
        total = e["price"] + (e["shipping"] or 0)
        table.add_row(e["searched_at"], e["source"], f"${total:.2f}", e["condition"] or "-")

    console.print(table)


if __name__ == "__main__":
    main()
