import re
import logging
from bookfinder.models import Condition

log = logging.getLogger(__name__)

def parse_price(text: str) -> float:
    """Extract numeric price from string (e.g. '$12.99' -> 12.99)."""
    if not text:
        return 0.0
    # Remove commas and handle multiple currency symbols
    cleaned = text.replace(",", "")
    match = re.search(r"[\d,]+\.?\d*", cleaned)
    try:
        return float(match.group()) if match else 0.0
    except ValueError:
        return 0.0

def parse_condition(text: str) -> Condition:
    """Parse book condition string into Condition enum."""
    if not text:
        return Condition.UNKNOWN
    text = text.lower()
    if "new" in text and "used" not in text:
        return Condition.NEW
    if "used" in text or "pre-owned" in text or "good" in text or "acceptable" in text:
        return Condition.USED
    return Condition.UNKNOWN

def parse_shipping(text: str) -> float | None:
    """Extract shipping cost from string (e.g. '+$3.50 shipping' -> 3.50)."""
    if not text:
        return None
    text_lower = text.lower()
    if "free" in text_lower:
        return 0.0
    
    # Try to find currency-prefixed price
    match = re.search(r"(?:US\$|\$)\s*([\d.]+)", text)
    if not match:
        # Fallback to just digits
        match = re.search(r"([\d.]+)\s*shipping", text_lower)
    
    try:
        return float(match.group(1)) if match else None
    except (ValueError, IndexError):
        return None
