"""Playwright helper for JS-rendered pages."""

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    return _PLAYWRIGHT_AVAILABLE


async def fetch_rendered_html(url: str, wait_selector: str | None = None, timeout: int = 15000) -> str:
    """Fetch a rendered page via headless Chromium."""
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. "
            "Install it with: pip install bookpricefinder[browser] && playwright install chromium"
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=timeout)
            else:
                await page.wait_for_timeout(2000)
            html = await page.content()
        finally:
            await browser.close()

    return html
