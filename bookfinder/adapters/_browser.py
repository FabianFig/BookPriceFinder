"""Playwright helper for JS-rendered pages with stealth support."""

import asyncio
import random

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    return _PLAYWRIGHT_AVAILABLE


async def fetch_rendered_html(url: str, wait_selector: str | None = None, timeout: int = 20000) -> str:
    """Fetch a rendered page via headless Chromium with stealth enabled."""
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. "
            "Install it with: pip install bookpricefinder[browser] && playwright install chromium"
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a more realistic context
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        page = await context.new_page()
        
        # Apply stealth
        await stealth_async(page)
        
        try:
            # Human-like delay before navigating
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout)
                except Exception:
                    # Fallback: if selector doesn't appear, just wait a bit more
                    await asyncio.sleep(3)
            else:
                await asyncio.sleep(3)
                
            html = await page.content()
        finally:
            await browser.close()

    return html
