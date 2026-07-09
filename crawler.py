"""
crawler.py
----------
Discovers all product URLs from a Shopify store using the built-in
/products.json API endpoint - no HTML parsing, no pagination guesswork.
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
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    api_base = f"{base}/products.json"

    logger.info("Crawling Shopify JSON API: %s", api_base)

    product_urls: list[str] = []
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
            logger.info("Page %d returned 0 products - crawl complete.", page)
            break

        for product in products:
            handle = product.get("handle", "")
            if handle and handle not in seen:
                seen.add(handle)
                product_urls.append(f"{base}/products/{handle}")

        logger.info(
            "Page %d - %d products (total so far: %d)",
            page, len(products), len(product_urls),
        )

        if len(products) < 250:
            logger.info("Last page reached.")
            break

        page += 1
        time.sleep(config.CRAWL_DELAY_SECONDS)

    logger.info("Crawl complete. Total product URLs: %d", len(product_urls))
    return product_urls