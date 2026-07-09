"""
app.py
------
Main entry point for the Website Image Downloader.

Run with:
    python app.py

Change START_URL (and any other setting) in config.py before running.
"""

import csv
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from tqdm import tqdm

import config
from crawler import discover_product_urls
from scraper import scrape_page
from downloader import download_images
from utils import get_logger, sanitize_folder_name, ensure_directory

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Full pipeline:
    1. Crawl the site to collect product URLs.
    2. Visit each product page to extract title + image URLs.
    3. Download and convert images into per-product folders.
    4. Write a CSV summary report.
    """
    start_time = time.time()
    output_root = Path(config.OUTPUT_FOLDER)
    ensure_directory(output_root)

    logger.info("=" * 60)
    logger.info("Website Image Downloader")
    logger.info("START_URL   : %s", config.START_URL)
    logger.info("OUTPUT      : %s", output_root.resolve())
    logger.info("FORMAT      : %s", config.OUTPUT_FORMAT.upper())
    logger.info("QUALITY     : %s", config.JPG_QUALITY if config.OUTPUT_FORMAT == "jpg" else config.WEBP_QUALITY)
    logger.info("THREADS     : %d", config.MAX_THREADS)
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Step 1 — Discover product URLs
    # ------------------------------------------------------------------
    print("\n🔍  Discovering product pages …")
    product_urls = discover_product_urls(config.START_URL)

    if not product_urls:
        logger.error("No product URLs found. Check START_URL and crawler heuristics.")
        return

    print(f"✅  Found {len(product_urls)} product pages.\n")

    # ------------------------------------------------------------------
    # Steps 2–6 — Scrape, download, convert
    # ------------------------------------------------------------------
    report_rows: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.HEADLESS)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

        progress = tqdm(
            product_urls,
            desc="Books processed",
            unit="page",
            ncols=72,
            bar_format="{desc}: {bar} {n_fmt}/{total_fmt}",
        )

        for url in progress:
            # Scrape title + image URLs.
            title, image_urls = scrape_page(page, url)
            safe_name = sanitize_folder_name(title)
            folder = output_root / safe_name

            progress.set_postfix_str(safe_name[:30], refresh=True)

            if not image_urls:
                logger.info("No images found on: %s", url)
                report_rows.append({"Book Name": title, "Images Downloaded": 0})
                continue

            # Download + convert images.
            count = download_images(image_urls, folder)
            report_rows.append({"Book Name": title, "Images Downloaded": count})
            logger.info("'%s' — %d image(s) saved", title, count)

            time.sleep(config.CRAWL_DELAY_SECONDS)

        browser.close()

    # ------------------------------------------------------------------
    # Step 9 — CSV report
    # ------------------------------------------------------------------
    report_path = output_root / config.REPORT_FILENAME
    _write_csv_report(report_rows, report_path)

    elapsed = time.time() - start_time
    total_images = sum(r["Images Downloaded"] for r in report_rows)

    print(f"\n🎉  Done in {elapsed:.1f}s")
    print(f"    Pages processed : {len(report_rows)}")
    print(f"    Images saved    : {total_images}")
    print(f"    Report          : {report_path}")
    print(f"    Output folder   : {output_root.resolve()}\n")


# ---------------------------------------------------------------------------
# CSV report
# ---------------------------------------------------------------------------

def _write_csv_report(rows: list[dict], path: Path) -> None:
    """
    Write the download summary to a CSV file at *path*.

    Args:
        rows: List of ``{"Book Name": str, "Images Downloaded": int}`` dicts.
        path: Destination file path.
    """
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Book Name", "Images Downloaded"])
            writer.writeheader()
            writer.writerows(rows)
        logger.info("CSV report written: %s", path)
    except OSError as exc:
        logger.error("Failed to write CSV report: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
