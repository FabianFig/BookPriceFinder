# Cleanup Audit Report: BookPriceFinder

This report outlines critical assessments and recommendations for codebase cleanup across 8 dimensions.

## 1. Deduplication & DRY
- **Adapters:** Nearly every adapter repeats the `async with httpx.AsyncClient(...)` pattern with similar timeouts and header usage. This should be abstracted into a base method in `BaseAdapter`.
- **Search Logic:** `search_all` and `search_all_with_report` in `search.py` share logic; `search_all` is just a thin wrapper.
- **Mapping Logic:** `cli.py` (line 155) manually reconstructs `BookResult`-like total price logic from DB dicts.
- **Web Params:** `web/main.py` duplicates search parameter dictionary construction in `search_post` and `save_search`.

## 2. Type Consolidation
- **Pydantic Models:** `SearchReport` lives in `search.py` but should be in `models.py`.
- **Database Returns:** `PriceDatabase` returns `list[dict]`. It should return Pydantic models (`list[BookResult]`, etc.) to maintain type safety throughout the app.
- **Wishlist Entry:** There is no model for a Wishlist entry; it's handled as raw dicts.

## 3. Dead Code Removal
- **Assets:** `bookfinder/web/static/rouby.jpg` is an unused personal asset.
- **Wrappers:** `search.search_all` is redundant.
- **Imports:** `bookfinder/search.py` imports `time` but `time.monotonic()` is used only once in a way that could be simplified or abstracted.

## 4. Dependency Resolution
- **Search vs DB:** `search.py` imports `PriceDatabase` solely for health logging, creating a dependency on the database layer for core search logic. Scraper health logging should be handled via a callback or event system.

## 5. Strict Typing
- **Any Usage:** `bookfinder/adapters/generic.py` uses `Any` in several function signatures.
- **Config:** `pyproject.toml` has `warn_return_any = false` and `ignore_missing_imports = true`. These should be tightened.
- **DB Layer:** Lack of models in return types results in implicit `Any` when accessing data in CLI and Web.

## 6. Error Handling
- **Broad Exceptions:** 
  - `adapters/base.py`: `except Exception as e` in `is_available`.
  - `search.py`: `except Exception as e` in `_safe_search`.
  - `web/main.py`: `except Exception:` in `convert_price`.
- **Hiding Errors:** Several places catch all exceptions and simply log a warning or return an empty list without preserving the original traceback or context.

## 7. Legacy Code
- **Proxies:** The recently removed `web.py` proxy pattern was fixed, but remnants of "offline mode" logic in `database.py` (`get_recent_results`) are identical to `get_price_history`.

## 8. AI Slop & Comments
- **Templates:** `results.html` and `wishlist.html` contain leftover comments from the "Rouby" vs "Generic" transition.
- **Docstrings:** Some docstrings are generic boilerplate that doesn't add value.
- **Unhelpful Notes:** "TODO" notes about personal photos and music links in templates should be removed for a clean codebase.
