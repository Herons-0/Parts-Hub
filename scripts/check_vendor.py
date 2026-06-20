"""Diagnose how an online store exposes its products, so we know which adapter to use.

Run it from YOUR machine (where the store is reachable):

    python scripts/check_vendor.py https://www.sharvielectronics.com
    python scripts/check_vendor.py https://flyrobo.in

It probes the common product feeds and inspects the homepage for platform
signatures, then prints a recommendation:
  - "shopify"     -> add to config with type "shopify" (or "auto")
  - "woocommerce" -> add with type "woocommerce" (or "auto")
  - "html-only"   -> needs a custom HTML scraper; share a product/category page
                     and we'll add CSS selectors.
"""
import sys
import httpx

UA = {"User-Agent": "Mozilla/5.0 (compatible; PartsHubBot/0.1)"}
TIMEOUT = 20.0


def _get(client, url):
    try:
        r = client.get(url)
        return r.status_code, r
    except Exception as exc:
        return None, str(exc)


def check(base: str) -> None:
    base = base.rstrip("/")
    print(f"\nProbing {base}\n" + "-" * (9 + len(base)))

    with httpx.Client(timeout=TIMEOUT, headers=UA, follow_redirects=True) as client:
        # 1) Shopify
        code, r = _get(client, f"{base}/products.json?limit=1")
        shopify_ok = False
        if code == 200 and not isinstance(r, str):
            try:
                n = len(r.json().get("products", []))
                shopify_ok = n > 0
                print(f"Shopify  /products.json          -> {code}, products: {n}")
            except Exception:
                print(f"Shopify  /products.json          -> {code}, not JSON")
        else:
            print(f"Shopify  /products.json          -> {code}")

        # 2) WooCommerce Store API
        code, r = _get(client, f"{base}/wp-json/wc/store/v1/products?per_page=1")
        woo_ok = False
        if code == 200 and not isinstance(r, str):
            try:
                woo_ok = len(r.json()) > 0
                print(f"Woo      /wp-json/wc/store/v1    -> {code}, products: {len(r.json())}")
            except Exception:
                print(f"Woo      /wp-json/wc/store/v1    -> {code}, not JSON")
        else:
            print(f"Woo      /wp-json/wc/store/v1    -> {code}")

        # 3) Homepage signature sniff
        code, r = _get(client, base)
        html = r.text.lower() if (code == 200 and not isinstance(r, str)) else ""
        sig = []
        if "cdn.shopify.com" in html or "shopify" in html:
            sig.append("shopify")
        if "woocommerce" in html or "wp-content" in html:
            sig.append("woocommerce/wordpress")
        if "magento" in html:
            sig.append("magento")
        print(f"Homepage                         -> {code}, signatures: {sig or 'none'}")

    # Recommendation
    print("\nRecommendation:")
    if shopify_ok:
        print('  type "shopify" (or "auto") -- /products.json works.')
    elif woo_ok:
        print('  type "woocommerce" (or "auto") -- Store API works.')
    elif "shopify" in (sig if 'sig' in dir() else []):
        print('  Looks like Shopify but feed was blocked. Try type "auto" from this machine.')
    elif sig and "woocommerce/wordpress" in sig:
        print('  Looks like WooCommerce but Store API is disabled.')
        print('  Needs an HTML scraper -- share a category/product page and we add selectors.')
    else:
        print('  No JSON feed detected. Likely custom/HTML-only.')
        print('  Share a category/product page URL and we add CSS selectors.')


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_vendor.py <store_url> [<store_url> ...]")
        raise SystemExit(1)
    for arg in sys.argv[1:]:
        check(arg)
