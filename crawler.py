"""
crawler.py
----------
Discovers all products from a Shopify store using the built-in
/products.json API endpoint.

Returns full product data including title and all image URLs directly
from the API — no browser visits needed, no rate limiting, no blocking.

Every Shopify store exposes:
  GET /products.json?limit=250&page=N

Each product in the response contains:
  - title        : product name (used as folder name)
  - handle       : URL slug
  - images       : list of image objects with src URLs
"""

import time
import requests
from urllib.parse import urlparse

import config
from utils import get_logger

logger = get_logger(__name__)

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
    Return all product page URLs from a Shopify store via the JSON API.
    Used for compatibility — main pipeline uses discover_all_products().

    Args:
        start_url: Any URL on the Shopify store.

    Returns:
        Deduplicated list of absolute product-page URLs.
    """
    products = discover_all_products(start_url)
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [f"{base}/products/{p['handle']}" for p in products if p.get("handle")]


def discover_all_products(start_url: str = config.START_URL) -> list[dict]:
    """
    Return all products from a Shopify store via the JSON API.

    Each returned dict contains:
      - title  : product name
      - handle : URL slug
      - images : list of full-resolution image URLs (query strings stripped)

    Args:
        start_url: Any URL on the Shopify store (we extract the base domain).

    Returns:
        List of product dicts with title and image URLs ready for download.
    """
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    api_base = f"{base}/products.json"

    logger.info("Crawling Shopify JSON API: %s", api_base)

    products_data: list[dict] = []
    seen: set[str] = set()
    page = 1

    while True:
        url = f"{api_base}?limit=250&page={page}"
        logger.info("Fetching page %d: %s", page, url)

        try:
            resp = _session.get(url, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            break

        products = data.get("products", [])

        if not products:
            logger.info("Page %d returned 0 products — crawl complete.", page)
            break

        for product in products:
            handle = product.get("handle", "")
            if not handle or handle in seen:
                continue
            seen.add(handle)

            # Extract full-resolution image URLs by stripping Shopify's
            # sizing query strings (e.g. ?v=123&width=533).
            image_urls = []
            for img in product.get("images", []):
                src = img.get("src", "")
                if src:
                    # Strip query string to get full resolution.
                    clean_src = src.split("?")[0]
                    image_urls.append(clean_src)

            products_data.append({
                "title":  product.get("title", handle),
                "handle": handle,
                "images": image_urls,
            })

        logger.info(
            "Page %d — %d products (total so far: %d)",
            page, len(products), len(products_data),
        )

        if len(products) < 250:
            logger.info("Last page reached.")
            break

        page += 1
        time.sleep(config.CRAWL_DELAY_SECONDS)

    logger.info("Crawl complete. Total products: %d", len(products_data))
    return products_data
