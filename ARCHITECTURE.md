# PartsHub — Architecture & System Design

A single place to search electronics products across multiple Indian online vendors,
compare prices, and organize parts into per-project bills of materials (BOMs).

> **Scope note (MVP):** This version is a *search + compare + BOM* aggregator. At
> checkout the user is handed off to each vendor's own site to pay. We do **not**
> store vendor logins or place orders on the user's behalf. See
> [Roadmap toward unified checkout](#7-roadmap-toward-unified-checkout) for why, and
> the realistic path to get closer to that vision.

---

## 1. The problem

Builders (students, clubs, hobbyists, startups) sourcing parts for a project must
hop between many vendor sites: search each one, track which part is cheaper/in stock
where, and manage several carts and orders. PartsHub collapses the *discovery and
planning* stage into one app.

## 2. What the MVP does

- **Unified search** across all configured vendors from one search box.
- **Price comparison** — when the same/similar part exists at multiple vendors,
  show them side by side (price, stock, vendor) so the user picks the best.
- **Project BOMs** — group parts into named projects (e.g. "Line-follower robot"),
  set quantities, and see a per-vendor subtotal and grand total.
- **Checkout handoff** — a BOM splits into per-vendor lists, each linking out to the
  vendor product pages to complete purchase. (Order tracking is a later phase.)

## 3. High-level architecture

```
                    ┌─────────────────────────────────────────────┐
                    │                  Browser                     │
                    │   HTML + CSS + a little vanilla JS           │
                    │   (search, compare, project/BOM pages)       │
                    └───────────────▲─────────────────────────────┘
                                    │ HTTP (HTML pages + JSON for JS)
                    ┌───────────────┴─────────────────────────────┐
                    │                FastAPI app                   │
                    │  routes → search.py → SQLite (FTS5)          │
                    │  Jinja2 templates render pages               │
                    └───────▲───────────────────────▲──────────────┘
                            │                       │
              reads/writes  │                       │ writes products
                            │                       │
                    ┌───────┴────────┐      ┌────────┴─────────────┐
                    │   SQLite DB    │◀─────│  Ingestion runner    │
                    │  products,     │      │  (scrapers/runner.py)│
                    │  projects,     │      │  run on a schedule   │
                    │  project_items │      │  or manually         │
                    └────────────────┘      └────────▲─────────────┘
                                                     │ HTTP
                                   ┌─────────────────┴───────────────────┐
                                   │   Vendor adapters                   │
                                   │   ShopifyAdapter  (products.json)   │
                                   │   WooAdapter      (Store API / HTML) │
                                   └─────────────────────────────────────┘
                                                     │
                              Robocraze · ThinkRobotics · QuartzComponents · …
```

The key design idea: **ingestion is decoupled from serving.** Scrapers run
periodically and write a normalized snapshot into SQLite. The web app only ever
reads from SQLite, so the site stays fast and keeps working even if a vendor site is
down or rate-limits us.

## 4. Components

### 4.1 Scrapers (data sourcing)
Each vendor is handled by an *adapter* that knows how to fetch that vendor's catalog
and return a list of normalized product dicts. Two adapter types cover most Indian
electronics stores:

- **`ShopifyAdapter`** — Shopify stores expose a public, paginated JSON feed at
  `/products.json?limit=250&page=N`. Confirmed working for **Robocraze,
  ThinkRobotics, QuartzComponents**. This is the cleanest, most reliable source
  (structured data, no HTML parsing). One adapter handles *any* Shopify store —
  adding a new one is a single config line.
- **`WooAdapter`** — WooCommerce stores (e.g. Robu.in) sometimes expose
  `/wp-json/wc/store/v1/products`; when disabled, fall back to parsing category
  pages with BeautifulSoup. Heavier and more fragile, so used only where needed.

All adapters output the same normalized shape (see [Data model](#5-data-model)), so
the rest of the system doesn't care where a product came from.

**Politeness & resilience:** small delay between requests, a real User-Agent,
pagination caps, timeouts, and per-vendor try/except so one bad vendor doesn't break
ingestion. Each run is *upsert-by* `(vendor, external_id)` so re-running refreshes
prices/stock instead of duplicating.

### 4.2 Database — SQLite
Chosen because it is zero-setup (a single file), built into Python, and supports
**FTS5** full-text search — ideal for a learnable project. Tables in §5.

### 4.3 Search & comparison — `search.py`
- **Search:** query the `products_fts` virtual table (FTS5) ranked by relevance,
  filterable by vendor / in-stock / price range.
- **Comparison:** group results that are likely the *same* part across vendors using
  a normalized title key + token-overlap (Jaccard) similarity, plus exact SKU match
  when available. Each group shows the cheapest in-stock option first.

### 4.4 Web app — FastAPI + Jinja2
Server-rendered HTML pages (easy to learn, no build step) with a sprinkle of vanilla
JS for add-to-project and live search. JSON endpoints back the JS.

## 5. Data model

```
products
  id              INTEGER PK
  vendor          TEXT      -- "robocraze"
  external_id     TEXT      -- vendor's own product id
  title           TEXT
  description     TEXT
  sku             TEXT
  brand           TEXT      -- Shopify "vendor" field (manufacturer)
  category        TEXT      -- product_type
  price           REAL      -- INR
  compare_at_price REAL     -- original/MRP if discounted
  currency        TEXT      -- "INR"
  in_stock        INTEGER   -- 0/1
  url             TEXT      -- canonical product page
  image           TEXT
  norm_key        TEXT      -- normalized title for grouping
  updated_at      TEXT
  UNIQUE(vendor, external_id)

products_fts  (FTS5 virtual table: title, brand, category, sku → rowid = products.id)

projects
  id          INTEGER PK
  name        TEXT
  created_at  TEXT

project_items
  id          INTEGER PK
  project_id  INTEGER FK → projects.id
  product_id  INTEGER FK → products.id
  quantity    INTEGER
  UNIQUE(project_id, product_id)
```

## 6. Request flows

**Search:** user types query → `GET /search?q=...` → FTS5 lookup → optionally group
by `norm_key` for comparison → render results.

**Add to project:** `POST /projects/{id}/items` (product_id, qty) → upsert
`project_items` → BOM page recomputes per-vendor subtotals and grand total.

**Checkout handoff:** BOM page groups items by vendor → each vendor block links to
its product pages → user opens vendor site(s) to pay. (No automation.)

## 7. Roadmap toward unified checkout

The original vision — sign in once, auto-fill every vendor's cart, pay inside our
app, place all orders — is the hardest and riskiest part:

- **No public ordering APIs.** Shopify/WooCommerce storefronts don't let third
  parties place orders for arbitrary shoppers.
- **Terms of Service.** Most vendors prohibit automated cart/checkout; storing user
  credentials for other sites is a security and legal liability.
- **Payments & PCI.** Handling other sites' payments would put us in scope for PCI
  compliance and card-network rules.

Realistic, lower-risk progression:

1. **Now (MVP):** unified search + compare + BOM + checkout handoff (this build).
2. **Cart deep-links:** Shopify supports permalink carts
   (`/cart/{variantId}:{qty},...`) — one click can pre-fill a vendor's cart, so the
   user just logs in and pays. Big UX win, still ToS-friendly.
3. **Order tracking:** let users paste order IDs / forward confirmation emails to
   track all orders in one dashboard.
4. **True unified checkout:** only via official distributor/reseller APIs
   (e.g. Mouser, Digi-Key) or formal partnerships with vendors — a business-deal
   problem more than an engineering one.

## 8. Tech stack

| Layer        | Choice                          | Why |
|--------------|---------------------------------|-----|
| Language     | Python 3.10+                    | Easy, great for scraping |
| Web framework| FastAPI + Uvicorn               | Simple, modern, auto API docs |
| Templates    | Jinja2                          | Server-rendered HTML, no build step |
| DB           | SQLite + FTS5 (stdlib `sqlite3`)| Zero-setup, full-text search |
| Scraping     | httpx + BeautifulSoup           | JSON feeds + HTML fallback |
| Frontend     | HTML + CSS + vanilla JS         | Easiest to learn, no framework |

## 9. Legal / ethical notes

- We ingest only **public** product-catalog data (Shopify `products.json` is a public
  endpoint), cache it, and link back to the vendor — similar to a price-comparison
  site. Still, check each vendor's `robots.txt` and Terms; be polite (rate-limit,
  identify the bot); and prefer official feeds/affiliate programs where they exist.
- Do **not** store users' vendor passwords or attempt automated checkout in this MVP.
- Product names, images, and descriptions belong to the vendors/brands; we display
  them with attribution and link to the source.
