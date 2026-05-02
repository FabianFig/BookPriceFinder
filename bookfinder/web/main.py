import csv
import io
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional, TypedDict
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from currency_converter import CurrencyConverter

from bookfinder.db.database import PriceDatabase
from bookfinder.web.utils import (
    apply_filters,
    apply_sort,
    bool_value,
    cached_search,
    compare_lowest_per_source,
    looks_like_isbn,
    paginate,
    get_book_cover_url,
)
from bookfinder.models import SearchReport, BookResult

log = logging.getLogger(__name__)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Strict types for context
class ContextDict(TypedDict, total=False):
    saved_searches: list[dict[str, Any]]
    display_currency: str
    available_currencies: list[str]
    query: str
    max_results: int
    sort_by: str
    filter_text: str
    min_price: str
    max_price: str
    condition_filter: str
    selected_sources: list[str]
    isbn_only: bool
    error: str
    results: list[BookResult]
    page_results: list[BookResult]
    total_results: int
    total_pages: int
    current_page: int
    compare_results: list[BookResult]
    sources: list[str]
    report: SearchReport
    entries: list[Any]
    add_title: str
    add_author: str
    add_isbn: str
    add_price: str
    health_groups: dict[str, list[Any]]

# Load currency converter once
converter: Optional[CurrencyConverter] = None
try:
    converter = CurrencyConverter()
except Exception as e:
    log.warning("Could not initialize currency converter: %s", e)

_RATE_LIMIT_SECONDS = 5
_LAST_SEARCH: dict[str, float] = defaultdict(float)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def get_common_context(db: PriceDatabase, request: Request) -> ContextDict:
    currency = request.cookies.get("bpf_currency", "USD")
    return {
        "saved_searches": db.list_saved_searches(),
        "display_currency": currency,
        "available_currencies": ["USD", "GBP", "EUR", "CAD", "AUD", "JPY"] if converter else ["USD"],
    }


def convert_price(price: float, from_curr: str, to_curr: str) -> float:
    if converter is None or from_curr == to_curr or price <= 0:
        return price
    try:
        return float(converter.convert(price, from_curr, to_curr))
    except Exception as e:
        log.debug("Conversion failed from %s to %s: %s", from_curr, to_curr, e)
        return price


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    with PriceDatabase() as db:
        context = await get_common_context(db, request)
    return templates.TemplateResponse(request, "index.html", context)  # type: ignore


@app.get("/search", response_class=HTMLResponse)
async def search_get(
    request: Request,
    query: str = Query(""),
    max_results: int = Query(5),
    sort_by: str = Query("price-asc"),
    filter: str = Query(""),
    min_price: Optional[str] = Query(None),
    max_price: Optional[str] = Query(None),
    condition: str = Query(""),
    sources: list[str] = Query([]),
    isbn_only: Optional[str] = Query(None),
    page: int = Query(1),
) -> HTMLResponse:
    with PriceDatabase() as db:
        context = await get_common_context(db, request)
        
        context.update({
            "query": query,
            "max_results": max_results,
            "sort_by": sort_by,
            "filter_text": filter,
            "min_price": min_price or "",
            "max_price": max_price or "",
            "condition_filter": condition,
            "selected_sources": sources,
            "isbn_only": bool_value(isbn_only) or looks_like_isbn(query),
        })

        if not query or not query.strip():
            return templates.TemplateResponse(request, "results.html", {**context, "page_results": []})  # type: ignore

        # Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        if now - _LAST_SEARCH[client_ip] < _RATE_LIMIT_SECONDS:
            context["error"] = "Please wait a few seconds."
            return templates.TemplateResponse(request, "results.html", {**context, "page_results": []})  # type: ignore
        _LAST_SEARCH[client_ip] = now

        isbn_flag = bool(context.get("isbn_only"))
        report = await cached_search(query, max_results, isbn_flag, db=db)
        results = report.results
        available_sources = sorted({r.source for r in results})

        def _to_float(v: Optional[str]) -> Optional[float]:
            try:
                return float(v) if v else None
            except ValueError:
                return None

        filtered = apply_filters(
            results,
            filter_text=filter,
            min_price=_to_float(min_price),
            max_price=_to_float(max_price),
            condition_filter=condition,
            selected_sources=sources,
            isbn_only=isbn_flag,
            isbn_query=query,
        )
        sorted_results = apply_sort(filtered, sort_by)
        
        target_curr = str(context.get("display_currency", "USD"))
        for r in sorted_results:
            if target_curr != r.currency:
                r.price = convert_price(r.price, r.currency, target_curr)
                if r.shipping is not None:
                    r.shipping = convert_price(r.shipping, r.currency, target_curr)
                r.currency = target_curr
            
            r.cover_url = get_book_cover_url(r.isbn)

            avg = db.get_average_price(isbn=r.isbn, title=r.title if not r.isbn else "")
            if avg and r.total_price > 0:
                score = (avg - r.total_price) / avg
                r.deal_score = max(-1.0, min(1.0, score))
            else:
                r.deal_score = 0.0

        page_results, total, total_pages, current_page = paginate(sorted_results, page, 25)

        context.update({
            "results": sorted_results,
            "page_results": page_results,
            "total_results": total,
            "total_pages": total_pages,
            "current_page": current_page,
            "compare_results": compare_lowest_per_source(sorted_results),
            "sources": available_sources,
            "report": report,
        })

        return templates.TemplateResponse(request, "results.html", context)  # type: ignore


@app.post("/search")
async def search_post(
    query: str = Form(...),
    max_results: int = Form(5),
    sort_by: str = Form("price-asc"),
    filter: str = Form(""),
    min_price: Optional[float] = Form(None),
    max_price: Optional[float] = Form(None),
    condition: str = Form(""),
    sources: list[str] = Form([]),
    isbn_only: Optional[str] = Form(None),
) -> RedirectResponse:
    params = {
        "query": query,
        "max_results": max_results,
        "sort_by": sort_by,
        "filter": filter,
        "min_price": min_price if min_price is not None else "",
        "max_price": max_price if max_price is not None else "",
        "condition": condition,
        "isbn_only": "1" if bool_value(isbn_only) else "",
        "sources": sources,
    }
    return RedirectResponse(url=f"/search?{urlencode(params, doseq=True)}", status_code=303)


@app.post("/set-currency")
async def set_currency(currency: str = Form(...)) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("bpf_currency", currency, max_age=31536000)
    return response


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request) -> HTMLResponse:
    with PriceDatabase() as db:
        context = await get_common_context(db, request)
        health_data = db.get_scraper_health()
    
    grouped: dict[str, list[Any]] = defaultdict(list)
    for entry in health_data:
        grouped[entry.source].append(entry)
    
    context["health_groups"] = dict(grouped)
    return templates.TemplateResponse(request, "status.html", context)  # type: ignore


@app.get("/api/history")
async def api_history(isbn: str = Query(""), title: str = Query("")) -> JSONResponse:
    with PriceDatabase() as db:
        history = db.get_price_history(isbn=isbn, title=title, limit=100)
    return JSONResponse([r.model_dump(mode='json') for r in history])


@app.post("/save-search")
async def save_search(
    name: str = Form(...),
    query: str = Form(""),
    max_results: int = Form(5),
    sort_by: str = Form("price-asc"),
    filter: str = Form(""),
    min_price: str = Form(""),
    max_price: str = Form(""),
    condition: str = Form(""),
    sources: str = Form(""),
    isbn_only: str = Form(""),
) -> RedirectResponse:
    params = {
        "query": query,
        "max_results": max_results,
        "sort_by": sort_by,
        "filter": filter,
        "min_price": min_price,
        "max_price": max_price,
        "condition": condition,
        "isbn_only": isbn_only,
        "sources": [s for s in sources.split(",") if s],
    }
    with PriceDatabase() as db:
        search_id = db.save_search(name, params)
    return RedirectResponse(url=f"/saved?id={search_id}", status_code=303)


@app.get("/saved", response_class=HTMLResponse)
async def saved_search(id: int = Query(...)) -> RedirectResponse:
    with PriceDatabase() as db:
        record = db.get_saved_search(id)
    if not record:
        return RedirectResponse(url="/")
    params = json.loads(record["params"])
    return RedirectResponse(url=f"/search?{urlencode(params, doseq=True)}")


@app.post("/delete-search")
async def delete_search(saved_id: int = Form(...)) -> RedirectResponse:
    with PriceDatabase() as db:
        db.delete_saved_search(saved_id)
    return RedirectResponse(url="/", status_code=303)


@app.get("/export")
async def export(
    query: str = Query(""),
    max_results: int = Query(5),
    sort_by: str = Query("price-asc"),
    filter: str = Query(""),
    min_price: Optional[str] = Query(None),
    max_price: Optional[str] = Query(None),
    condition: str = Query(""),
    sources: list[str] = Query([]),
    isbn_only: Optional[str] = Query(None),
) -> StreamingResponse:
    isbn_flag = bool_value(isbn_only)
    report = await cached_search(query, max_results, isbn_flag)
    
    def _to_float(v: Optional[str]) -> Optional[float]:
        try:
            return float(v) if v else None
        except ValueError:
            return None

    filtered = apply_filters(
        report.results,
        filter_text=filter,
        min_price=_to_float(min_price),
        max_price=_to_float(max_price),
        condition_filter=condition,
        selected_sources=sources,
        isbn_only=isbn_flag,
        isbn_query=query,
    )
    sorted_results = apply_sort(filtered, sort_by)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["source", "title", "author", "price", "currency", "condition", "url"])
    for r in sorted_results:
        writer.writerow([r.source, r.title, r.author, f"{r.total_price:.2f}", r.currency, r.condition.value, r.url])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bookpricefinder.csv"},
    )


@app.get("/wishlist", response_class=HTMLResponse)
async def wishlist_page(
    request: Request,
    add_title: str = Query(""),
    add_author: str = Query(""),
    add_isbn: str = Query(""),
    add_price: str = Query(""),
) -> HTMLResponse:
    with PriceDatabase() as db:
        context = await get_common_context(db, request)
        entries = db.get_wishlist()
    
    context.update({
        "entries": entries,
        "add_title": add_title,
        "add_author": add_author,
        "add_isbn": add_isbn,
        "add_price": add_price,
    })
    return templates.TemplateResponse(request, "wishlist.html", context)  # type: ignore


@app.post("/wishlist/add")
async def wishlist_add(
    title: str = Form(...),
    author: str = Form(""),
    isbn: str = Form(""),
    max_price: Optional[float] = Form(None),
) -> RedirectResponse:
    with PriceDatabase() as db:
        db.add_to_wishlist(title, author, isbn, max_price)
    return RedirectResponse(url="/wishlist", status_code=303)


@app.post("/wishlist/import")
async def wishlist_import(file: UploadFile = File(...)) -> RedirectResponse:
    content = await file.read()
    text = content.decode("utf-8")
    import re
    isbns = re.findall(r"\b(?:97[89])?\d{9}[\dX]\b", text)
    with PriceDatabase() as db:
        for isbn in isbns:
            db.add_to_wishlist(f"Imported ISBN {isbn}", "", isbn)
    return RedirectResponse(url="/wishlist", status_code=303)


@app.post("/wishlist/delete")
async def wishlist_delete(wishlist_id: int = Form(...)) -> RedirectResponse:
    with PriceDatabase() as db:
        db.remove_from_wishlist(wishlist_id)
    return RedirectResponse(url="/wishlist", status_code=303)
