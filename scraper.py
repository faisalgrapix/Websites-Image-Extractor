"""
scraper.py
----------
Visits a single product/book page and extracts:
  - The page title (used as the output folder name).
  - All relevant product image URLs (filtered for quality and relevance).

Uses Playwright for rendering and BeautifulSoup for parsing, so it works on
both static HTML and JavaScript-heavy pages.
"""

import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

import config
from utils import get_logger, is_svg_url

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_page(page: Page, url: str) -> tuple[str, list[str]]:
    """
    Load *url* in the given Playwright *page* and extract the title + images.

    Args:
        page: An already-open Playwright :class:`Page` instance.
        url:  Absolute URL of the product/book page to scrape.

    Returns:
        A tuple of ``(title, image_urls)`` where:
        - *title* is the page/product title (falls back to the URL slug).
        - *image_urls* is an ordered, deduplicated list of absolute image URLs
          ready for downloading.
    """
    logger.debug("Scraping page: %s", url)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(config.PAGE_LOAD_WAIT_MS / 1000)
        html = page.content()
    except Exception as exc:
        logger.error("Failed to load product page %s: %s", url, exc)
        return _url_slug(url), []

    soup = BeautifulSoup(html, "lxml")

    title = _extract_title(soup, url)
    image_urls = _extract_image_urls(soup, url)

    logger.debug(
        "Page '%s' — found %d images", title, len(image_urls)
    )
    return title, image_urls


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup, url: str) -> str:
    """
    Extract the most meaningful title from the page.

    Tries (in order):
    1. ``<h1>`` — most reliable for product pages.
    2. ``<title>`` tag (stripped of common suffixes like "| Site Name").
    3. URL slug as a last resort.

    Args:
        soup: Parsed page HTML.
        url:  Page URL (fallback slug source).

    Returns:
        Raw title string (sanitization happens later in :mod:`utils`).
    """
    # 1. Primary heading
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(separator=" ", strip=True)
        if text:
            return text

    # 2. <title> tag — strip everything after the first "|", "–", or "—"
    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        for separator in ("|", "–", "—", "-", "::"):
            if separator in raw:
                raw = raw.split(separator)[0].strip()
        if raw:
            return raw

    # 3. Fallback: derive a title from the URL path
    return _url_slug(url)


def _url_slug(url: str) -> str:
    """Convert the last meaningful path segment of *url* into a readable title."""
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1] if path else url
    # Replace hyphens/underscores with spaces and title-case.
    return slug.replace("-", " ").replace("_", " ").title() or "Untitled"


# ---------------------------------------------------------------------------
# Image URL extraction
# ---------------------------------------------------------------------------

def _extract_image_urls(soup: BeautifulSoup, page_url: str) -> list[str]:
    """
    Find all product-relevant ``<img>`` src values in *soup*.

    Filtering rules applied:
    - Skip SVG files (logos, icons).
    - Skip images whose URL contains any pattern from
      :data:`config.IGNORE_URL_PATTERNS`.
    - Skip ``data:`` URIs (inline images, usually placeholders).
    - Prefer ``data-src`` / ``data-lazy-src`` over ``src`` to handle
      lazy-loading libraries.
    - Deduplicate by normalised URL (query strings stripped).

    Args:
        soup:     Parsed page HTML.
        page_url: Absolute URL of the page (used to resolve relative hrefs).

    Returns:
        Ordered, deduplicated list of absolute image URLs.
    """
    seen_normalised: set[str] = set()
    urls: list[str] = []

    for img in soup.find_all("img"):
        # Prefer lazy-load src attributes when present.
        src: str = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or img.get("src")
            or ""
        ).strip()

        if not src:
            continue

        # Skip inline data URIs.
        if src.startswith("data:"):
            continue

        absolute = urljoin(page_url, src)

        # Shopify CDN appends sizing params like ?v=123&width=533 which
        # return thumbnails instead of full-resolution images. Strip them.
        absolute = absolute.split("?")[0]

        # Skip SVGs.
        if is_svg_url(absolute):
            logger.debug("Skipping SVG: %s", absolute)
            continue

        # Skip URLs matching ignore patterns.
        lower = absolute.lower()
        if any(pattern in lower for pattern in config.IGNORE_URL_PATTERNS):
            logger.debug("Skipping ignored URL pattern: %s", absolute)
            continue

        # Deduplicate by URL without query string.
        normalised = absolute.split("?")[0].split("#")[0]
        if normalised in seen_normalised:
            continue
        seen_normalised.add(normalised)

        urls.append(absolute)

    return urls
