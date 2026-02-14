"""Minimal web UI powered by FastAPI."""

import csv
import html
import io
import time
from collections import defaultdict
from math import ceil
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from bookfinder.db.database import PriceDatabase
from bookfinder.models import BookQuery
from bookfinder.search import SearchReport, search_all_with_report

app = FastAPI()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ITEMS = 50
_CACHE: dict[tuple[str, int, bool], tuple[float, SearchReport]] = {}

# Rate limiting: per-IP cooldown
_RATE_LIMIT_SECONDS = 5
_LAST_SEARCH: dict[str, float] = defaultdict(float)


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _build_query(params: dict) -> str:
    return urlencode(params, doseq=True)


def _bool_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


async def _cached_search(query: str, max_results: int, isbn_only: bool) -> SearchReport:
    key = (query, max_results, isbn_only)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    book_query = BookQuery(
        query="" if isbn_only else query,
        isbn=query if isbn_only else "",
        max_results=max_results,
    )
    report = await search_all_with_report(book_query)
    _CACHE[key] = (now, report)

    if len(_CACHE) > _CACHE_MAX_ITEMS:
        oldest_key = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest_key, None)

    return report


def _render_page(
    content: str = "",
    query: str = "",
    max_results: int = 5,
    page_size: int = 25,
    sort_by: str = "price-asc",
    filter_text: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    condition_filter: str = "",
    sources: list[str] | None = None,
    selected_sources: list[str] | None = None,
    isbn_only: bool = False,
) -> HTMLResponse:
    sources = sources or []
    selected_sources = selected_sources or []
    all_selected = bool(sources) and len(selected_sources) == len(set(sources))

    checkboxes = "".join(
        f"<label><input type=\"checkbox\" name=\"sources\" value=\"{_esc(s)}\""
        f" {'checked' if s in selected_sources else ''} /> { _esc(s) }</label>"
        for s in sorted(set(sources))
    )

    with PriceDatabase() as db:
        saved = db.list_saved_searches()

    saved_options = "".join(
        f"<option value=\"{s['id']}\">{_esc(s['name'])}</option>" for s in saved
    )

    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>BookPriceFinder</title>
        <style>
          :root {{ --bg: #ffffff; --text: #111111; --muted: #666; --border: #ddd; --head: #f5f5f5; }}
          [data-theme="dark"] {{ --bg: #0f1115; --text: #f0f0f0; --muted: #9aa0a6; --border: #2a2f3a; --head: #1a1f27; }}
          body {{ font-family: system-ui, sans-serif; margin: 2rem; background: var(--bg); color: var(--text); }}
          input, button, select {{ padding: 0.5rem; font-size: 1rem; }}
          .controls {{ display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; margin-top: 0.75rem; }}
          .controls label {{ display: inline-flex; gap: 0.4rem; align-items: center; }}
          .preset-row {{ display: flex; gap: 0.5rem; align-items: center; margin-top: 0.75rem; }}
          .section {{ margin-top: 1rem; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
          th, td {{ border: 1px solid var(--border); padding: 0.5rem; text-align: left; }}
          th {{ background: var(--head); }}
          .muted {{ color: var(--muted); font-size: 0.9rem; }}
          @media (max-width: 768px) {{
            body {{ margin: 0.75rem; }}
            table {{ font-size: 0.85rem; display: block; overflow-x: auto; }}
            .controls {{ flex-direction: column; align-items: flex-start; }}
            input, button, select {{ width: 100%; box-sizing: border-box; }}
            h1 {{ font-size: 1.4rem; }}
          }}
        </style>
      </head>
      <body>
        <h1>BookPriceFinder</h1>
        <form method="post" action="/search" id="searchForm">
          <input name="query" placeholder="Search books" required value="{_esc(query)}" />
          <input name="max_results" type="number" min="1" max="50" value="{max_results}" />
          <input name="page_size" type="number" min="5" max="100" value="{page_size}" />
          <button type="submit" id="searchBtn">Search</button>
          <button type="button" id="themeToggle">Toggle theme</button>
          <div class="controls">
            <label>
              <input type="checkbox" name="isbn_only" value="1" {'checked' if isbn_only else ''} /> Use ISBN
            </label>
            <label>
              Sort by
              <select name="sort_by">
                <option value="price-asc" {'selected' if sort_by == 'price-asc' else ''}>Price (low → high)</option>
                <option value="price-desc" {'selected' if sort_by == 'price-desc' else ''}>Price (high → low)</option>
                <option value="title-asc" {'selected' if sort_by == 'title-asc' else ''}>Title (A → Z)</option>
                <option value="title-desc" {'selected' if sort_by == 'title-desc' else ''}>Title (Z → A)</option>
                <option value="source-asc" {'selected' if sort_by == 'source-asc' else ''}>Source (A → Z)</option>
                <option value="source-desc" {'selected' if sort_by == 'source-desc' else ''}>Source (Z → A)</option>
              </select>
            </label>
            <label>
              Filter
              <input name="filter" placeholder="type to filter results" value="{_esc(filter_text)}" />
            </label>
            <label>
              Min price
              <input name="min_price" type="number" step="0.01" placeholder="0.00" value="{min_price or ''}" />
            </label>
            <label>
              Max price
              <input name="max_price" type="number" step="0.01" placeholder="99.99" value="{max_price or ''}" />
            </label>
            <label>
              Condition
              <select name="condition">
                <option value="" {'selected' if condition_filter == '' else ''}>Any</option>
                <option value="new" {'selected' if condition_filter == 'new' else ''}>new</option>
                <option value="used" {'selected' if condition_filter == 'used' else ''}>used</option>
                <option value="unknown" {'selected' if condition_filter == 'unknown' else ''}>unknown</option>
              </select>
            </label>
          </div>
          <div class="controls">
            <span class="muted">Sources:</span>
            <label><input type="checkbox" id="toggleAllSources" {'checked' if all_selected else ''} /> All</label>
            {checkboxes or '<span class="muted">(search to load sources)</span>'}
          </div>
        </form>

        <div class="section">
          <strong>Saved searches</strong>
          <div class="preset-row">
            <select id="savedSelect">
              <option value="">Load saved search…</option>
              {saved_options}
            </select>
            <button type="button" id="loadSaved">Load</button>
            <form method="post" action="/delete-search">
              <input type="hidden" name="saved_id" id="deleteSavedId" />
              <button type="submit">Delete</button>
            </form>
          </div>
        </div>

        {content}

        <script>
          const savedSelect = document.getElementById('savedSelect');
          const loadBtn = document.getElementById('loadSaved');
          const deleteId = document.getElementById('deleteSavedId');
          const themeToggle = document.getElementById('themeToggle');
          const allToggle = document.getElementById('toggleAllSources');

          loadBtn?.addEventListener('click', () => {{
            const id = savedSelect.value;
            if (!id) return;
            window.location.href = `/saved?id=${{id}}`;
          }});

          savedSelect?.addEventListener('change', () => {{
            deleteId.value = savedSelect.value;
          }});

          themeToggle?.addEventListener('click', () => {{
            const current = document.body.getAttribute('data-theme') || 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', next);
            localStorage.setItem('bpf-theme', next);
          }});

          const savedTheme = localStorage.getItem('bpf-theme');
          if (savedTheme) {{
            document.body.setAttribute('data-theme', savedTheme);
          }}

          allToggle?.addEventListener('change', () => {{
            const checked = allToggle.checked;
            document.querySelectorAll('input[name="sources"]').forEach(cb => {{
              cb.checked = checked;
            }});
          }});

          document.getElementById('searchForm')?.addEventListener('submit', () => {{
            const btn = document.getElementById('searchBtn');
            if (btn) {{
              btn.disabled = true;
              btn.textContent = 'Searching...';
            }}
          }});
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index():
    return _render_page()


def _apply_filters(
    results,
    filter_text: str,
    min_price: float | None,
    max_price: float | None,
    condition_filter: str,
    selected_sources: list[str],
    isbn_only: bool,
    isbn_query: str,
):
    if filter_text:
        needle = filter_text.lower()
        results = [
            r for r in results if needle in f"{r.title} {r.author} {r.source}".lower()
        ]

    if min_price is not None:
        results = [r for r in results if r.total_price >= min_price]
    if max_price is not None:
        results = [r for r in results if r.total_price <= max_price]

    if condition_filter:
        results = [r for r in results if r.condition.value == condition_filter]

    if selected_sources:
        results = [r for r in results if r.source in selected_sources]

    if isbn_only and isbn_query:
        results = [r for r in results if r.isbn == isbn_query]

    return results


def _apply_sort(results, sort_by: str):
    if sort_by == "price-desc":
        results.sort(key=lambda r: r.total_price, reverse=True)
    elif sort_by == "title-asc":
        results.sort(key=lambda r: r.title)
    elif sort_by == "title-desc":
        results.sort(key=lambda r: r.title, reverse=True)
    elif sort_by == "source-asc":
        results.sort(key=lambda r: r.source)
    elif sort_by == "source-desc":
        results.sort(key=lambda r: r.source, reverse=True)
    else:
        results.sort(key=lambda r: r.total_price)
    return results


def _paginate(results, page: int, page_size: int):
    total = len(results)
    total_pages = max(1, ceil(total / page_size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return results[start:end], total, total_pages, page


def _compare_lowest_per_source(results):
    lowest = {}
    for r in results:
        if r.price <= 0:
            continue
        cur = lowest.get(r.source)
        if not cur or r.total_price < cur.total_price:
            lowest[r.source] = r
    return list(lowest.values())


def _render_results(
    results,
    query: str,
    max_results: int,
    page_size: int,
    page: int,
    sort_by: str,
    filter_text: str,
    min_price: float | None,
    max_price: float | None,
    condition: str,
    sources: list[str],
    selected_sources: list[str],
    isbn_only: bool,
    report: SearchReport | None = None,
):
    if not results:
        return _render_page(
            "<p>No results found.</p>",
            query=query,
            max_results=max_results,
            page_size=page_size,
            sort_by=sort_by,
            filter_text=filter_text,
            min_price=min_price,
            max_price=max_price,
            condition_filter=condition,
            sources=sources,
            selected_sources=selected_sources,
            isbn_only=isbn_only,
        )

    # Source status summary
    source_status = ""
    if report:
        status_parts = []
        for name, count in sorted(report.source_counts.items()):
            status_parts.append(f"{_esc(name)}: {count} results")
        for name, err in sorted(report.errors.items()):
            status_parts.append(f"<span style='color:red'>{_esc(name)}: failed</span>")
        if status_parts:
            source_status = f"<p class='muted'>{' &middot; '.join(status_parts)}</p>"

    compare = _compare_lowest_per_source(results)
    compare_rows = "".join(
        f"<tr><td>{_esc(r.source)}</td><td>{_esc(r.title)}</td>"
        f"<td>${r.total_price:.2f}</td><td>{_esc(r.condition.value)}</td>"
        f"<td><a href='{_esc(r.url)}' target='_blank'>link</a></td></tr>"
        for r in compare
    )
    compare_table = f"""
    <h3>Lowest price per source</h3>
    <table>
      <thead>
        <tr><th>Source</th><th>Title</th><th>Price</th><th>Condition</th><th>URL</th></tr>
      </thead>
      <tbody>{compare_rows}</tbody>
    </table>
    """

    page_results, total, total_pages, current_page = _paginate(results, page, page_size)

    rows = "".join(
        f"<tr><td>{_esc(r.source)}</td><td>{_esc(r.title)}</td><td>{_esc(r.author)}</td>"
        f"<td>${r.total_price:.2f}</td><td>{_esc(r.condition.value)}</td>"
        f"<td><a href='{_esc(r.url)}' target='_blank'>link</a></td></tr>"
        for r in page_results
    )

    table = f"""
    <h3>Results ({total} total)</h3>
    <table>
      <thead>
        <tr>
          <th>Source</th><th>Title</th><th>Author</th>
          <th>Price</th><th>Condition</th><th>URL</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """

    params = dict(
        query=query,
        max_results=max_results,
        page_size=page_size,
        sort_by=sort_by,
        filter=filter_text,
        min_price=min_price or "",
        max_price=max_price or "",
        condition=condition,
        isbn_only="1" if isbn_only else "",
        sources=selected_sources,
    )

    pagination_links = " ".join(
        f"<a href=\"/search?{_build_query({**params, 'page': p})}\">{p}</a>"
        if p != current_page
        else f"<strong>{p}</strong>"
        for p in range(1, total_pages + 1)
    )
    pagination = f"<div class=\"section\">Pages: {pagination_links}</div>"

    save_form = f"""
    <div class=\"section\">
      <form method=\"post\" action=\"/save-search\">
        <input name=\"name\" placeholder=\"Save search name\" required />
        <input type=\"hidden\" name=\"query\" value=\"{_esc(query)}\" />
        <input type=\"hidden\" name=\"max_results\" value=\"{max_results}\" />
        <input type=\"hidden\" name=\"page_size\" value=\"{page_size}\" />
        <input type=\"hidden\" name=\"sort_by\" value=\"{_esc(sort_by)}\" />
        <input type=\"hidden\" name=\"filter\" value=\"{_esc(filter_text)}\" />
        <input type=\"hidden\" name=\"min_price\" value=\"{min_price or ''}\" />
        <input type=\"hidden\" name=\"max_price\" value=\"{max_price or ''}\" />
        <input type=\"hidden\" name=\"condition\" value=\"{_esc(condition)}\" />
        <input type=\"hidden\" name=\"isbn_only\" value=\"{'1' if isbn_only else ''}\" />
        <input type=\"hidden\" name=\"sources\" value=\"{_esc(','.join(selected_sources))}\" />
        <button type=\"submit\">Save this search</button>
      </form>
    </div>
    """

    # Build sources hidden inputs outside f-string to avoid Python 3.10 escape issues
    sources_inputs = ''.join(
        f'<input type="hidden" name="sources" value="{_esc(s)}" />'
        for s in selected_sources
    )

    export_form = f"""
    <form method=\"get\" action=\"/export\" style=\"margin-top: 0.75rem;\">
      <input type=\"hidden\" name=\"query\" value=\"{_esc(query)}\" />
      <input type=\"hidden\" name=\"max_results\" value=\"{max_results}\" />
      <input type=\"hidden\" name=\"sort_by\" value=\"{_esc(sort_by)}\" />
      <input type=\"hidden\" name=\"filter\" value=\"{_esc(filter_text)}\" />
      <input type=\"hidden\" name=\"min_price\" value=\"{min_price or ''}\" />
      <input type=\"hidden\" name=\"max_price\" value=\"{max_price or ''}\" />
      <input type=\"hidden\" name=\"condition\" value=\"{_esc(condition)}\" />
      <input type=\"hidden\" name=\"isbn_only\" value=\"{'1' if isbn_only else ''}\" />
      {sources_inputs}
      <button type=\"submit\">Export CSV</button>
    </form>
    """

    return _render_page(
        source_status + save_form + compare_table + table + pagination + export_form,
        query=query,
        max_results=max_results,
        page_size=page_size,
        sort_by=sort_by,
        filter_text=filter_text,
        min_price=min_price,
        max_price=max_price,
        condition_filter=condition,
        sources=sources,
        selected_sources=selected_sources,
        isbn_only=isbn_only,
    )


@app.get("/search", response_class=HTMLResponse)
async def search_get(
    request: Request,
    query: str = Query(""),
    max_results: int = Query(5),
    page_size: int = Query(25),
    page: int = Query(1),
    sort_by: str = Query("price-asc"),
    filter: str = Query(""),
    min_price: str | None = Query(None),
    max_price: str | None = Query(None),
    condition: str = Query(""),
    sources: list[str] = Query([]),
    isbn_only: str | None = Query(None),
):
    if not query or not query.strip():
        return _render_page("<p>Please enter a search query.</p>")

    def _to_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    min_val = _to_float(min_price)
    max_val = _to_float(max_price)
    isbn_flag = _bool_value(isbn_only)

    # Per-IP rate limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    if now - _LAST_SEARCH[client_ip] < _RATE_LIMIT_SECONDS:
        return _render_page(
            "<p>Please wait a few seconds between searches.</p>",
            query=query,
        )
    _LAST_SEARCH[client_ip] = now

    report = await _cached_search(query, max_results, isbn_flag)
    results = report.results
    available_sources = sorted({r.source for r in results})

    filtered = _apply_filters(
        results,
        filter_text=filter,
        min_price=min_val,
        max_price=max_val,
        condition_filter=condition,
        selected_sources=sources,
        isbn_only=isbn_flag,
        isbn_query=query,
    )
    sorted_results = _apply_sort(filtered, sort_by)

    return _render_results(
        sorted_results,
        query=query,
        max_results=max_results,
        page_size=page_size,
        page=page,
        sort_by=sort_by,
        filter_text=filter,
        min_price=min_val,
        max_price=max_val,
        condition=condition,
        sources=available_sources,
        selected_sources=sources,
        isbn_only=isbn_flag,
        report=report,
    )


@app.post("/search")
async def search_post(
    query: str = Form(...),
    max_results: int = Form(5),
    page_size: int = Form(25),
    sort_by: str = Form("price-asc"),
    filter: str = Form(""),
    min_price: float | None = Form(None),
    max_price: float | None = Form(None),
    condition: str = Form(""),
    sources: list[str] = Form([]),
    isbn_only: str | None = Form(None),
) -> RedirectResponse | HTMLResponse:
    if not query or not query.strip():
        return _render_page("<p>Please enter a search query.</p>")

    params = dict(
        query=query,
        max_results=max_results,
        page_size=page_size,
        page=1,
        sort_by=sort_by,
        filter=filter,
        min_price=min_price or "",
        max_price=max_price or "",
        condition=condition,
        isbn_only="1" if _bool_value(isbn_only) else "",
        sources=sources,
    )
    return RedirectResponse(url=f"/search?{_build_query(params)}", status_code=303)


@app.post("/save-search")
async def save_search(
    name: str = Form(...),
    query: str = Form(""),
    max_results: int = Form(5),
    page_size: int = Form(25),
    sort_by: str = Form("price-asc"),
    filter: str = Form(""),
    min_price: str = Form(""),
    max_price: str = Form(""),
    condition: str = Form(""),
    sources: str = Form(""),
    isbn_only: str = Form(""),
):
    params = dict(
        query=query,
        max_results=max_results,
        page_size=page_size,
        sort_by=sort_by,
        filter=filter,
        min_price=min_price,
        max_price=max_price,
        condition=condition,
        isbn_only=isbn_only,
        sources=[s for s in sources.split(",") if s],
    )

    with PriceDatabase() as db:
        search_id = db.save_search(name, params)

    return RedirectResponse(url=f"/saved?id={search_id}", status_code=303)


@app.get("/saved", response_class=HTMLResponse)
async def saved_search(id: int = Query(...)):
    with PriceDatabase() as db:
        record = db.get_saved_search(id)

    if not record:
        return _render_page("<p>Saved search not found.</p>")

    params = __import__("json").loads(record["params"])
    query = params.get("query", "")
    max_results = int(params.get("max_results", 5))
    page_size = int(params.get("page_size", 25))
    sort_by = params.get("sort_by", "price-asc")
    filter_text = params.get("filter", "")
    min_price = params.get("min_price") or None
    max_price = params.get("max_price") or None
    condition = params.get("condition", "")
    sources = params.get("sources", [])
    isbn_only = _bool_value(params.get("isbn_only"))

    report = await _cached_search(query, max_results, isbn_only)
    available_sources = sorted({r.source for r in report.results})

    filtered = _apply_filters(
        report.results,
        filter_text=filter_text,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        condition_filter=condition,
        selected_sources=sources,
        isbn_only=isbn_only,
        isbn_query=query,
    )
    sorted_results = _apply_sort(filtered, sort_by)

    return _render_results(
        sorted_results,
        query=query,
        max_results=max_results,
        page_size=page_size,
        page=1,
        sort_by=sort_by,
        filter_text=filter_text,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        condition=condition,
        sources=available_sources,
        selected_sources=sources,
        isbn_only=isbn_only,
        report=report,
    )


@app.post("/delete-search")
async def delete_search(saved_id: int = Form(...)):
    with PriceDatabase() as db:
        db.delete_saved_search(saved_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/export")
async def export(
    query: str = Query(""),
    max_results: int = Query(5),
    sort_by: str = Query("price-asc"),
    filter: str = Query(""),
    min_price: str | None = Query(None),
    max_price: str | None = Query(None),
    condition: str = Query(""),
    sources: list[str] = Query([]),
    isbn_only: str | None = Query(None),
):
    def _to_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    min_val = _to_float(min_price)
    max_val = _to_float(max_price)
    isbn_flag = _bool_value(isbn_only)

    results = await _cached_search(query, max_results, isbn_flag)
    filtered = _apply_filters(
        results,
        filter_text=filter,
        min_price=min_val,
        max_price=max_val,
        condition_filter=condition,
        selected_sources=sources,
        isbn_only=isbn_flag,
        isbn_query=query,
    )
    sorted_results = _apply_sort(filtered, sort_by)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["source", "title", "author", "price", "condition", "url"])
    for r in sorted_results:
        writer.writerow(
            [r.source, r.title, r.author, f"{r.total_price:.2f}", r.condition.value, r.url]
        )

    output.seek(0)
    filename = "bookpricefinder.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
