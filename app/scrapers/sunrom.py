"""Sunrom Electronics adapter (https://www.sunrom.com).

Sunrom runs on a custom platform (not Shopify/WooCommerce), so we scrape its HTML
listing pages with BeautifulSoup.

Catalog structure (observed):
  - All products live under /c/products, paginated: /c/products?page=N&per-page=48
  - Each product card is a link to /p/<slug> whose content includes:
        "Product Code: <id>"   -> stable numeric id (we use it as external_id + sku)
        "Rs.<price>/-"         -> price in INR
        an <img alt="title">   -> product title + image
  - ~3157 products => ~66 pages at 48/page.

The parser is text/regex based (reads the card's visible text + image), so it does
not depend on Sunrom's exact CSS class names and is resilient to minor markup changes.
"""
import re
import time
import httpx
from bs4 import BeautifulSoup

from ..config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_PAGES_PER_VENDOR
from .base import normalized_product, to_float

CODE_RE = re.compile(r"Product\s*Code:\s*(\d+)", re.I)
PRICE_RE = re.compile(r"Rs\.?\s*([\d,]+\.?\d*)\s*/-", re.I)

# Sunrom shows 48 items/page; its "All Products" category needs ~66 pages.
PER_PAGE = 48
PAGE_CAP = max(MAX_PAGES_PER_VENDOR, 80)


def fetch_products(vendor: dict) -> list[dict]:
    base = vendor["base_url"].rstrip("/")
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    results: list[dict] = []
    seen: set[str] = set()

    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers, follow_redirects=True) as client:
        for page in range(1, PAGE_CAP + 1):
            url = f"{base}/c/products?page={page}&per-page={PER_PAGE}"
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except Exception as exc:
                print(f"  [{vendor['name']}] page {page} failed: {exc}")
                break

            cards = parse_listing(resp.text, base, vendor)
            new = [c for c in cards if c["external_id"] not in seen]
            if not new:
                break  # no new products -> reached the end

            for c in new:
                seen.add(c["external_id"])
                results.append(c)
            time.sleep(REQUEST_DELAY)

    return results


def parse_listing(html: str, base: str, vendor: dict) -> list[dict]:
    """Parse one listing page's HTML into normalized product dicts."""
    soup = BeautifulSoup(html, "html.parser")

    # Group all anchors that point to a product (/p/<slug>) by their slug, so an
    # image-link and a text-link for the same product get merged.
    cards: dict[str, dict] = {}
    for a in soup.select('a[href*="/p/"]'):
        href = a.get("href", "")
        if "/p/" not in href:
            continue
        slug = href.split("/p/")[-1].split("?")[0].strip("/")
        if not slug:
            continue
        entry = cards.setdefault(slug, {"href": href, "text": "", "img": None})
        entry["text"] += " " + a.get_text(" ", strip=True)
        if entry["img"] is None:
            img = a.find("img")
            if img is not None:
                entry["img"] = img

    out: list[dict] = []
    for slug, entry in cards.items():
        text = entry["text"]
        code_m = CODE_RE.search(text)
        if not code_m:
            continue  # not a real product card (e.g. a category/nav link)
        code = code_m.group(1)

        price_m = PRICE_RE.search(text)
        price = to_float(price_m.group(1)) if price_m else None

        img = entry["img"]
        title = ""
        image = ""
        if img is not None:
            title = (img.get("alt") or "").strip()
            image = img.get("src") or ""
            if image.startswith("//"):
                image = "https:" + image
            elif image.startswith("/"):
                image = base + image
        if not title:
            title = _title_from_slug(slug)

        href = entry["href"]
        url = href if href.startswith("http") else base + href

        out.append(normalized_product(
            vendor=vendor["name"],
            vendor_label=vendor["label"],
            external_id=code,
            title=title,
            sku=code,
            brand="",
            category="",
            price=price,
            currency=vendor.get("currency", "INR"),
            in_stock=True,
            url=url,
            image=image,
        ))
    return out


def _title_from_slug(slug: str) -> str:
    """Fallback title derived from the URL slug, e.g. 'white-side-led-0805'."""
    return slug.replace("-", " ").strip().title()
