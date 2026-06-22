"""Robu.in adapter — headless Next.js storefront backed by a custom GraphQL API.

Robu.in does NOT expose a Shopify/WooCommerce feed: the site is a Next.js single-page
app whose product data comes from a GraphQL endpoint the browser calls. Discovered by
inspecting the live site's network traffic:

    endpoint : POST https://robu.in/api/proxy/graphql        (Content-Type: application/json)
    operation: visibleMenuCategories(parent:true, slug, page, limit, sort, search, filters)
    path     : data.visibleMenuCategories.data[0].products[]
    fields   : id, sku, name, slug, price, sale_price, moq_price, images[], in_stock,
               mpn, categories

We paginate each TOP-LEVEL category (parent:true returns the whole subtree) and
de-duplicate products by id, since a product can appear under several categories.

Notes / caveats:
  - Robu sits behind Cloudflare, so we send browser-like headers. If a datacenter IP
    gets a 403 challenge, run ingestion from a normal residential network.
  - This is a private/undocumented API and can change without notice — it's more
    fragile than the public-feed vendors. Re-capture the query if the schema changes.
"""
import time
import httpx

from .base import normalized_product, to_float
from ..config import REQUEST_TIMEOUT, REQUEST_DELAY

GRAPHQL_URL = "https://robu.in/api/proxy/graphql"

# Top-level, product-bearing categories (extracted from robu's mega-menu).
# parent:true makes each one return products from its entire subtree.
ROBU_CATEGORIES = [
    "smartelex",
    "electronic-modules",
    "electronic-components",
    "microcontroller-development-board",
    "sensor-modules",
    "iot-and-wireless",
    "dc-motors",
    "drone-parts",
    "simplifly-drone-parts",
    "3d-printer-parts",
    "batteries",
    "ebike-parts",
    "mechanical-parts-and-tools",
    "learning-and-robotic-kits",
]

# Minimal query requesting only the fields we store (the endpoint accepts arbitrary
# queries). Mirrors the site's own "CategoryProducts" operation.
CAT_QUERY = (
    "query Cat($slug:String!,$limit:Int,$page:Int){"
    " visibleMenuCategories(parent:true, slug:$slug, limit:$limit, page:$page,"
    " sort:\"\", search:\"\", filters:[]){"
    " status message data { products {"
    " id sku name slug price sale_price moq_price images in_stock mpn categories"
    " } } } }"
)

PER_PAGE = 100
MAX_PAGES_PER_CATEGORY = 80

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://robu.in",
    "Referer": "https://robu.in/shop/",
}


def fetch_products(vendor: dict) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        for slug in ROBU_CATEGORIES:
            for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
                payload = {
                    "operationName": "Cat",
                    "query": CAT_QUERY,
                    "variables": {"slug": slug, "limit": PER_PAGE, "page": page},
                }
                try:
                    resp = client.post(GRAPHQL_URL, json=payload)
                    if resp.status_code != 200:
                        print(f"  [{vendor['name']}] {slug} page {page}: HTTP {resp.status_code}")
                        break
                    body = resp.json()
                except Exception as exc:
                    print(f"  [{vendor['name']}] {slug} page {page} error: {exc}")
                    break

                products = _extract_products(body)
                new = 0
                for p in products:
                    pid = "" if p.get("id") in (None, "") else str(p.get("id"))
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    rec = _normalize(vendor, p)
                    if rec["title"]:
                        results.append(rec)
                        new += 1

                print(f"    [{vendor['name']}] {slug} page {page} (+{new}, total {len(results)})")
                if new == 0 or len(products) < PER_PAGE:
                    break  # category exhausted
                time.sleep(REQUEST_DELAY)

    if not results:
        print(f"  [{vendor['name']}] no products returned — robu's API may be "
              f"Cloudflare-blocking this network, or its GraphQL schema changed.")
    return results


def _extract_products(body: dict) -> list[dict]:
    """Pull the product list out of the GraphQL response (data may be a list or dict)."""
    vmc = (body.get("data") or {}).get("visibleMenuCategories") or {}
    data = vmc.get("data")
    if isinstance(data, dict):
        entries = list(data.values())
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    products: list[dict] = []
    for entry in entries:
        if isinstance(entry, dict):
            products.extend(entry.get("products") or [])
    return products


def _normalize(vendor: dict, p: dict) -> dict:
    images = p.get("images") or []
    image = images[0] if images else ""

    # Effective selling price: sale_price when present, else regular price.
    sale = to_float(p.get("sale_price"))
    regular = to_float(p.get("price"))
    price = sale if sale else regular
    compare_at = regular if (sale and regular and regular > sale) else None

    cats = p.get("categories")
    if isinstance(cats, list):
        category = ", ".join(str(c) for c in cats[:3])
    else:
        category = str(cats or "")

    slug = p.get("slug") or ""
    return normalized_product(
        vendor=vendor["name"],
        vendor_label=vendor["label"],
        external_id=str(p.get("id")),
        title=p.get("name", ""),
        sku=str(p.get("sku") or ""),
        brand="",
        category=category,
        price=price,
        compare_at_price=compare_at,
        currency=vendor.get("currency", "INR"),
        in_stock=bool(p.get("in_stock")),
        url=f"https://robu.in/product/{slug}/" if slug else "https://robu.in/",
        image=image,
    )
