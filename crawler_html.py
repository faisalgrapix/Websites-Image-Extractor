"""
crawler_html.py
---------------
Discovers all product/page URLs from ANY website using HTML scraping.
Works on Squarespace, Wix, Magento, custom sites, or any site without an API.

HOW TO USE
----------
1. Rename this file to crawler.py (replace the existing one)
2. In config.py set:
       START_URL = "https://yoursite.com/shop"  (or any listing/category page)
3. Tune the settings in the CONFIGURATION section below to match your site.

HOW TO FIND YOUR SETTINGS
--------------------------
1. Open your target website in Chrome
2. Right-click on a product link -> Inspect
3. Look at the href of product links — note the URL pattern
   Example: /products/book-name or /shop/item/book-name
4. Add that pattern to PRODUCT_PATH_SIGNALS below
5. Look for the "next page" button and note its HTML structure
   Then adjust NEXT_PAGE_TEXTS or NEXT_PAGE_CLASS below

COMMON PATTERNS BY PLATFORM
-----------------------------
Squarespace : product URLs contain /products/ or /store/
Wix         : product URLs contain /product-page/
Magento     : product URLs end in .html or contain /catalog/product/
Custom site : inspect the HTML and find the pattern yourself
"""

import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser

import config
from utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# CONFIGURATION — tune these for your specific website
# ---------------------------------------------------------------------------

# URL path segments that identify a PRODUCT page.
# Add whatever pattern your site uses.
# Examples:
#   Squarespace : "/products/"
#   Wix         : "/product-page/"
#   Magento     : "/catalog/product/"
#   Custom      : "/item/", "/book/", "/listing/"
PRODUCT_PATH_SIGNALS: tuple[str, ...] = (
    "/products/",
    "/product/",
    "/product-page/",
    "/shop/",
    "/item/",
    "/book/",
    "/listing/",
    "/catalog/product/",
    "/store/",
    "/p/",
)

# URL path segments that identify NON-product pages to skip.
SKIP_PATH_SIGNALS: tuple[str, ...] = (
    "/cart",
    "/checkout",
    "/account",
    "/login",
    "/register",
    "/search",
    "/blog",
    "/news",
    "/about",
    "/contact",
    "/faq",
    "/policies",
    "/cdn/",
    "/tags/",
    "/collections",   # Shopify category pages
    "/category/",     # WordPress category pages
)

# Text content of "next page" links.
# Add whatever your site uses.
NEXT_PAGE_TEXTS: set[str] = {
    "next", "next page", "→", ">", "»", "›",
    "load more", "show more", "more products",
}

# CSS class of the "next page" container (if your site uses Bootstrap pagination).
# Common values: "next", "pagination-next", "next-page"
NEXT_PAGE_CLASS: str = "next"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_product_urls(start_url: str = config.START_URL) -> list[str]:
    """
    Crawl *start_url* and return all product page URLs found.

    Uses a real Playwright browser so it works on JavaScript-rendered sites
    (Squarespace, Wix, etc.) as well as plain HTML sites.

    Args:
        start_url: Entry point — usually a shop/category/listing page.

    Returns:
        Deduplicated list of absolute product-page URLs.
    """
    logger.info("Starting HTML crawl from: %s", start_url)

    product_urls: list[str] = []
    seen_products: set[str] = set()
    visited_listing_pages: set[str] = set()

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=config.HEADLESS)
        page: Page = browser.new_page()

        page.set_extra_http_headers({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

        current_url: str | None = start_url

        while current_url:
            # Avoid infinite loops.
            normalised = current_url.split("?")[0].rstrip("/")
            if normalised in visited_listing_pages:
                logger.debug("Already visited: %s", current_url)
                break
            visited_listing_pages.add(normalised)

            logger.info("Crawling listing page: %s", current_url)

            try:
                page.goto(current_url, wait_until="domcontentloaded", timeout=30_000)
                # Extra wait for JS-heavy sites (Wix, Squarespace).
                time.sleep(config.PAGE_LOAD_WAIT_MS / 1000)

                # Scroll to bottom to trigger lazy-loaded product grids.
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.5)

                html = page.content()
            except Exception as exc:
                logger.error("Failed to load %s: %s", current_url, exc)
                break

            soup = BeautifulSoup(html, "lxml")

            # Collect product URLs from this listing page.
            new_urls = _extract_product_urls(soup, current_url, start_url)
            added = 0
            for url in new_urls:
                norm = url.split("?")[0].rstrip("/")
                if norm not in seen_products:
                    seen_products.add(norm)
                    product_urls.append(url)
                    added += 1

            logger.info(
                "Found %d new product URLs on this page (total: %d)",
                added, len(product_urls),
            )

            # Follow pagination.
            current_url = _find_next_page(soup, current_url)
            if current_url:
                time.sleep(config.CRAWL_DELAY_SECONDS)

        browser.close()

    logger.info("HTML crawl complete. Total product URLs: %d", len(product_urls))
    return product_urls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_product_urls(
    soup: BeautifulSoup,
    current_url: str,
    start_url: str,
) -> list[str]:
    """
    Find all product-page links in *soup*.

    Args:
        soup:        Parsed HTML of a listing page.
        current_url: URL of the listing page (for resolving relative hrefs).
        start_url:   Original start URL (for same-origin filtering).

    Returns:
        List of absolute product-page URLs.
    """
    start_netloc = urlparse(start_url).netloc
    results: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href: str = anchor["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue

        absolute = urljoin(current_url, href)
        parsed = urlparse(absolute)

        # Same origin only.
        if parsed.netloc and parsed.netloc != start_netloc:
            continue

        path = parsed.path.lower()

        # Must match a product signal.
        if not any(signal in path for signal in PRODUCT_PATH_SIGNALS):
            continue

        # Must not match a skip signal.
        if any(skip in path for skip in SKIP_PATH_SIGNALS):
            continue

        results.append(absolute)

    return results


def _find_next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """
    Find the "next page" link in *soup* and return its absolute URL.

    Tries multiple common pagination patterns:
    1. <li class="next"><a href="...">
    2. <a rel="next" href="...">
    3. Any <a> whose text matches NEXT_PAGE_TEXTS
    4. ?page=N style URL increment

    Args:
        soup:        Parsed HTML of the current listing page.
        current_url: Current page URL.

    Returns:
        Absolute URL of the next page, or None if not found.
    """
    # Pattern 1: Bootstrap-style <li class="next">
    next_li = soup.find("li", class_=NEXT_PAGE_CLASS)
    if next_li:
        anchor = next_li.find("a", href=True)
        if anchor:
            return urljoin(current_url, anchor["href"])

    # Pattern 2: <a rel="next">
    rel_next = soup.find("a", rel="next")
    if rel_next and rel_next.get("href"):
        return urljoin(current_url, rel_next["href"])

    # Pattern 3: anchor text matches known "next" phrases
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(strip=True).lower()
        if text in NEXT_PAGE_TEXTS:
            return urljoin(current_url, anchor["href"])

    # Pattern 4: ?page=N increment
    from urllib.parse import parse_qs, urlencode, urlunparse
    parsed = urlparse(current_url)
    qs = parse_qs(parsed.query)
    current_page = int(qs.get("page", ["1"])[0])
    next_page = current_page + 1
    qs["page"] = [str(next_page)]
    next_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    # Only follow if a link to the next page exists in the HTML.
    for anchor in soup.find_all("a", href=True):
        if f"page={next_page}" in anchor["href"]:
            return next_url

    return None
