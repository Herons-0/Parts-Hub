"""Auto-detecting adapter for onboarding a store without knowing its platform.

Strategy (in order, stops at the first that returns products):
  1. Shopify   -> <base>/products.json
  2. WooCommerce Store API -> <base>/wp-json/wc/store/v1/products

This is ideal for newly onboarded vendors: set type="auto" in config and the
ingestion run figures out the platform on its own. If neither feed returns data
(e.g. the store is custom-built or only exposes HTML), it returns an empty list and
prints guidance to run the diagnostic script and add HTML selectors.

Note: some stores (e.g. Sharvi Electronics, FlyRobo) block server/datacenter IPs,
so these feeds may return nothing in a sandbox but work when ingestion runs from
your own machine/network.
"""
from . import shopify, woocommerce


def fetch_products(vendor: dict) -> list[dict]:
    name = vendor["name"]

    # 1) Try Shopify's products.json
    try:
        records = shopify.fetch_products(vendor)
        if records:
            print(f"  [{name}] auto-detected platform: Shopify ({len(records)} products)")
            return records
    except Exception as exc:
        print(f"  [{name}] Shopify probe failed: {exc}")

    # 2) Try WooCommerce: Store API first, then HTML shop-page scraping
    #    (woocommerce.fetch_products handles both, with a browser User-Agent).
    try:
        records = woocommerce.fetch_products(vendor)
        if records:
            print(f"  [{name}] auto-detected platform: WooCommerce ({len(records)} products)")
            return records
    except Exception as exc:
        print(f"  [{name}] WooCommerce probe failed: {exc}")

    print(
        f"  [{name}] auto-detect found no products via Shopify or WooCommerce.\n"
        f"           Run:  python scripts/check_vendor.py {vendor['base_url']}\n"
        f"           If it's a custom/HTML-only store, we'll add a dedicated scraper."
    )
    return []
