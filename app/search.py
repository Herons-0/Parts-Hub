"""Search and price-comparison logic.

Two public functions:
- search_products(): full-text search with filters, ranked by relevance.
- compare_group(): given a product, find likely-equivalent listings at other vendors
  so the user can compare price/stock.
"""
import sqlite3

from .database import db, normalize_title


def _fts_query(q: str) -> str:
    """Turn a user query into a safe FTS5 MATCH expression.

    We quote each token and add a prefix '*' so partial words match
    (e.g. "arduin" matches "arduino"). Tokens are AND-ed together.
    """
    tokens = [t for t in "".join(c if c.isalnum() else " " for c in q).split() if t]
    if not tokens:
        return ""
    return " AND ".join(f'"{t}"*' for t in tokens)


def search_products(
    q: str,
    *,
    vendor: str | None = None,
    in_stock_only: bool = False,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str = "relevance",
    limit: int = 60,
) -> list[dict]:
    """Search products with optional filters. Returns a list of row dicts."""
    match = _fts_query(q)
    params: list = []
    where: list[str] = []

    if match:
        base = (
            "SELECT p.*, bm25(products_fts) AS rank "
            "FROM products_fts "
            "JOIN products p ON p.id = products_fts.rowid "
            "WHERE products_fts MATCH ? "
        )
        params.append(match)
    else:
        # Empty query -> browse newest/all products.
        base = "SELECT p.*, 0 AS rank FROM products p WHERE 1=1 "

    if vendor:
        where.append("p.vendor = ?")
        params.append(vendor)
    if in_stock_only:
        where.append("p.in_stock = 1")
    if min_price is not None:
        where.append("p.price >= ?")
        params.append(min_price)
    if max_price is not None:
        where.append("p.price <= ?")
        params.append(max_price)

    if where:
        base += "AND " + " AND ".join(where) + " "

    order = {
        "price_asc": "p.price ASC",
        "price_desc": "p.price DESC",
        "relevance": "rank ASC" if match else "p.updated_at DESC",
    }.get(sort, "rank ASC" if match else "p.updated_at DESC")
    base += f"ORDER BY {order} LIMIT ?"
    params.append(limit)

    with db() as conn:
        rows = conn.execute(base, params).fetchall()
    return [dict(r) for r in rows]


def _jaccard(a: str, b: str) -> float:
    """Token-overlap similarity between two normalized keys (0..1)."""
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def compare_group(product_id: int, threshold: float = 0.55) -> list[dict]:
    """Return listings (across all vendors) that look like the same part.

    Strategy:
      1. Exact match on `norm_key` (cheap, catches obvious duplicates).
      2. Same SKU at another vendor (strong signal when present).
      3. Fuzzy: token-overlap (Jaccard) >= threshold against the source title.
    Always includes the source product. Sorted cheapest in-stock first.
    """
    with db() as conn:
        src = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not src:
            return []
        src = dict(src)
        norm = src["norm_key"] or normalize_title(src["title"])

        # Candidate pool: same norm_key, same SKU, or sharing the first token.
        first_token = norm.split()[0] if norm else ""
        rows = conn.execute(
            """
            SELECT * FROM products
            WHERE norm_key = ?
               OR (sku != '' AND sku = ?)
               OR norm_key LIKE ?
            """,
            (norm, src["sku"], f"%{first_token}%"),
        ).fetchall()

    matches = {}
    for r in rows:
        r = dict(r)
        same = (
            r["id"] == src["id"]
            or r["norm_key"] == norm
            or (src["sku"] and r["sku"] == src["sku"])
            or _jaccard(norm, r["norm_key"] or "") >= threshold
        )
        if same:
            matches[r["id"]] = r

    matches.setdefault(src["id"], src)
    result = list(matches.values())
    # Cheapest in-stock first; out-of-stock and missing prices sink to the bottom.
    result.sort(key=lambda x: (
        0 if x["in_stock"] else 1,
        x["price"] if x["price"] is not None else float("inf"),
    ))
    return result
