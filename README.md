# PartsHub ⚡

A single place to **search electronics parts across multiple Indian vendors**,
**compare prices**, and build a **per-project bill of materials (BOM)** — instead of
hopping between vendor websites.

Built with **FastAPI + SQLite + Jinja2 (HTML/CSS/vanilla JS)** — a simple, beginner-
friendly stack. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design and the
roadmap toward unified checkout.

## Features (MVP)
- 🔎 **Unified search** across all configured vendors (FTS5 full-text search)
- ⚖️ **Price comparison** — same part across vendors, cheapest in-stock first
- 📋 **Project BOMs** — group parts into projects with quantities and per-vendor subtotals
- 🛒 **Checkout handoff** — each vendor block links out to the store to order

## Vendors included
Robocraze, ThinkRobotics, QuartzComponents (Shopify), Sharvi Electronics and
FlyRobo (`type: "auto"`, platform detected at ingestion time), Sunrom Electronics
(custom platform, dedicated HTML scraper), Sun Electronics
(`sunelectronics.co.in`, WooCommerce Store API), and Ktron (`www.ktron.in`,
`type: "auto"`). Add more in [`app/config.py`](app/config.py) — for any
Shopify/WooCommerce store it's a single entry.

> **Onboarding a new store:** if you're unsure of its platform, run
> `python scripts/check_vendor.py <store_url>` from your machine. It reports whether
> the store is Shopify, WooCommerce, or HTML-only and which `type` to use. Some
> stores block datacenter IPs, so always run ingestion/diagnostics from your own
> network.

## Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. install dependencies
pip install -r requirements.txt

# 3a. load REAL product data from the live vendor catalogs
python -m scripts.ingest

#     ...or 3b. just load a small demo dataset to try the UI instantly
python -m scripts.seed_demo

# 4. start the web app
uvicorn app.main:app --reload

# 5. open http://127.0.0.1:8000
```

> Run `python -m scripts.ingest` from the **project root** (the folder with this
> README), not from inside `scripts/`.

## How it works
1. **Ingestion** (`scripts/ingest.py` → `app/scrapers/`) fetches each vendor's public
   product catalog and stores a normalized snapshot in `partshub.db` (SQLite).
2. **The web app** (`app/main.py`) only reads from SQLite, so the site stays fast and
   keeps working even if a vendor is down. Re-run ingestion to refresh prices/stock.

## Refreshing the catalog
Re-run `python -m scripts.ingest` periodically (e.g. a daily Windows Task Scheduler
job or cron) to keep prices and stock current.

## Project layout
```
app/
  main.py            FastAPI routes + page rendering
  config.py          vendor list + scraping settings
  database.py        SQLite schema, connection, title normalization
  search.py          full-text search + price-comparison grouping
  projects.py        project / BOM operations
  scrapers/
    base.py          shared helpers + normalized product shape
    shopify.py       Shopify /products.json adapter (works for any Shopify store)
    woocommerce.py   WooCommerce Store-API + HTML-fallback adapter
    runner.py        ingest all vendors → upsert into SQLite
  templates/         Jinja2 HTML
  static/            style.css + app.js
scripts/
  ingest.py          run live ingestion
  seed_demo.py       load a tiny demo dataset
```

## Notes & limitations
- This MVP **does not** store vendor logins or place orders automatically — see the
  roadmap in `ARCHITECTURE.md` for why and the realistic path forward.
- Only public catalog data is ingested and cached, with links back to each vendor.
  Be polite (the scraper rate-limits and identifies itself) and review each vendor's
  Terms before scaling up.
