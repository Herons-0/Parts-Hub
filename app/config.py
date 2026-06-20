"""Central configuration: the database location and the list of vendors to ingest.

To add a new Shopify-based vendor, just append a dict with type "shopify" and the
store's base URL. That's the whole change needed for ingestion.
"""
import os
from pathlib import Path

# Project root (folder that contains this app/ package)
BASE_DIR = Path(__file__).resolve().parent.parent

# Single SQLite file lives in the project root by default.
# Override with the PARTSHUB_DB environment variable (e.g. to use a faster local
# disk if the project lives on a network/mounted drive).
DB_PATH = Path(os.environ.get("PARTSHUB_DB", BASE_DIR / "partshub.db"))

# Vendors to ingest. Each entry is one online store.
#   name     : short slug used internally and shown as the vendor label
#   label    : nice display name
#   type     : "shopify"     -> uses /products.json
#              "woocommerce" -> uses the WooCommerce Store API (+ HTML fallback)
#              "auto"        -> tries Shopify, then WooCommerce, uses whichever works
#                              (best for new stores when you don't know the platform)
#   base_url : store homepage, no trailing slash
#   currency : ISO currency code for prices
VENDORS = [
    {
        "name": "robocraze",
        "label": "Robocraze",
        "type": "shopify",
        "base_url": "https://robocraze.com",
        "currency": "INR",
    },
    {
        "name": "thinkrobotics",
        "label": "ThinkRobotics",
        "type": "shopify",
        "base_url": "https://thinkrobotics.com",
        "currency": "INR",
    },
    {
        "name": "quartzcomponents",
        "label": "QuartzComponents",
        "type": "shopify",
        "base_url": "https://quartzcomponents.com",
        "currency": "INR",
    },
    # --- Onboarded with auto-detection. These stores block datacenter IPs, so the
    # platform is detected at ingestion time from your machine. If "auto" finds no
    # JSON feed, run `python scripts/check_vendor.py <url>` to see what's available
    # and we can add HTML selectors. ---
    {
        "name": "sharvielectronics",
        "label": "Sharvi Electronics",
        "type": "auto",
        "base_url": "https://www.sharvielectronics.com",
        "currency": "INR",
    },
    {
        "name": "flyrobo",
        "label": "FlyRobo",
        "type": "auto",
        "base_url": "https://flyrobo.in",
        "currency": "INR",
    },
    # Sunrom Electronics runs on a custom platform (no JSON feed), so it has a
    # dedicated HTML scraper (app/scrapers/sunrom.py).
    {
        "name": "sunrom",
        "label": "Sunrom Electronics",
        "type": "sunrom",
        "base_url": "https://www.sunrom.com",
        "currency": "INR",
    },
    # Sun Electronics (Kanpur) is WooCommerce with the Store API enabled, so the
    # standard WooCommerce adapter handles it directly.
    {
        "name": "sunelectronics",
        "label": "Sun Electronics",
        "type": "woocommerce",
        "base_url": "https://sunelectronics.co.in",
        "currency": "INR",
    },
    # Ktron blocks datacenter IPs, so its platform couldn't be detected from the
    # build sandbox. "auto" detects Shopify/WooCommerce at ingestion time from your
    # machine; if it finds no JSON feed, run scripts/check_vendor.py and we'll add a
    # dedicated HTML scraper.
    {
        "name": "ktron",
        "label": "Ktron",
        "type": "auto",
        "base_url": "https://www.ktron.in",
        "currency": "INR",
    },
    # Example of a WooCommerce vendor (HTML/Store-API fallback). Disabled by default
    # because it needs more tuning than the Shopify feeds.
    # {
    #     "name": "robu",
    #     "label": "Robu.in",
    #     "type": "woocommerce",
    #     "base_url": "https://robu.in",
    #     "currency": "INR",
    # },
]

# Polite scraping settings.
USER_AGENT = (
    "PartsHubBot/0.1 (student project; aggregates public product catalogs; "
    "contact: you@example.com)"
)
REQUEST_TIMEOUT = 20.0      # seconds per HTTP request
REQUEST_DELAY = 0.5         # seconds to wait between paginated requests
MAX_PAGES_PER_VENDOR = 40   # safety cap (40 * 250 = up to 10k products/vendor)
