"""
crawler_woocommerce.py
----------------------
Discovers all product URLs from a WooCommerce (WordPress) store using the
WooCommerce REST API.

HOW TO USE
----------
1. Rename this file to crawler.py (replace the existing one)
2. In config.py set:
       START_URL = "https://yoursite.com"
3. You need WooCommerce API keys:
   - Go to: WP Admin -> WooCommerce -> Settings -> Advanced -> REST API
   - Click "Add Key"
   - Set permissions to "Read"
   - Copy the Consumer Key and Consumer Secret below

IMPORTANT
---------
The WooCommerce REST API requires authentication.
Never share or commit your API keys to GitHub.
Add this to your .gitignore if you store keys in a separate file.
"""

import time
import requests
from urllib.parse import urlparse

import config
from utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# WooCommerce API credentials
# Paste your keys here — get them from:
# WP Admin -> WooCommerce -> Settings -> Advanced -> REST API
# ---------------------------------------------------------------------------
WC_CONSUMER_KEY    = "ck_your_consumer_key_here"
WC_CONSUMER_SECRET = "cs_your_consumer_secret_here"

# How many products to fetch per API request (max 100 for WooCommerce).
WC_PER_PAGE = 100

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
})


def discover_product_urls(start_url: str = config.START_URL) -> list[str]:
    """
    Return all product page URLs from a WooCommerce store via the REST API.

    Uses /wp-json/wc/v3/products?per_page=100&page=N — the standard
    WooCommerce REST API endpoint available on every WooCommerce store.

    Args:
        start_url: Any URL on the WooCommerce site (we extract the base domain).

    Returns:
        Deduplicated list of absolute product-page URLs.
    """
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    api_base = f"{base}/wp-json/wc/v3/products"

    logger.info("Crawling WooCommerce REST API: %s", api_base)

    # Check if API credentials are set.
    if "your_consumer_key_here" in WC_CONSUMER_KEY:
        logger.error(
            "WooCommerce API keys not set. "
            "Edit crawler_woocommerce.py and add your Consumer Key and Secret."
        )
        return []

    product_urls: list[str] = []
    seen: set[str] = set()
    page = 1

    while True:
        logger.info("Fetching page %d from WooCommerce API", page)

        try:
            resp = _session.get(
                api_base,
                params={
                    "per_page": WC_PER_PAGE,
                    "page": page,
                    "status": "publish",   # only published products
                },
                auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET),
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            products = resp.json()
        except requests.HTTPError as exc:
            if exc.response.status_code == 401:
                logger.error(
                    "Authentication failed. Check your Consumer Key and Secret."
                )
            else:
                logger.error("API request failed: %s", exc)
            break
        except Exception as exc:
            logger.error("Failed to fetch products page %d: %s", page, exc)
            break

        if not products:
            logger.info("Page %d returned 0 products — crawl complete.", page)
            break

        for product in products:
            # WooCommerce returns the full permalink directly.
            url = product.get("permalink", "")
            slug = product.get("slug", "")

            if url and url not in seen:
                seen.add(url)
                product_urls.append(url)
            elif slug and slug not in seen:
                # Fallback: build URL from slug.
                fallback = f"{base}/product/{slug}/"
                seen.add(slug)
                product_urls.append(fallback)

        logger.info(
            "Page %d — %d products (total so far: %d)",
            page, len(products), len(product_urls),
        )

        # WooCommerce returns fewer than per_page on the last page.
        if len(products) < WC_PER_PAGE:
            logger.info("Last page reached.")
            break

        page += 1
        time.sleep(config.CRAWL_DELAY_SECONDS)

    logger.info("Crawl complete. Total product URLs: %d", len(product_urls))
    return product_urls
