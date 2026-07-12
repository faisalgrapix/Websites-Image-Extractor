"""
app.py
------
Main entry point for the Website Image Downloader.

Run with:
    python app.py

Change START_URL (and any other setting) in config.py before running.

Pipeline (Shopify API mode - fast, no blocking):
  1. Fetch all products + image URLs directly from /products.json API
  2. Download and convert images into per-product folders
  3. Write a CSV summary report

No browser visits to individual product pages — everything comes from
the Shopify JSON API, which is fast, reliable and never rate-limits images.
"""

import csv
import time
from pathlib import Path

from tqdm import tqdm

import config
from crawler import discover_all_products
from downloader import download_images
from utils import get_logger, sanitize_folder_name, ensure_directory

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Full pipeline:
    1. Fetch all product data (title + images) from Shopify JSON API.
    2. Download and convert images into per-product folders.
    3. Write a CSV summary report.
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
    # Step 1 — Fetch all products + image URLs from Shopify API
    # ------------------------------------------------------------------
    print("\n🔍  Fetching product data from Shopify API …")
    products = discover_all_products(config.START_URL)

    if not products:
        logger.error("No products found. Check START_URL in config.py.")
        return

    total_api_images = sum(len(p["images"]) for p in products)
    print(f"✅  Found {len(products)} products with {total_api_images} images total.\n")

    # ------------------------------------------------------------------
    # Steps 2 — Download and convert images
    # ------------------------------------------------------------------
    report_rows: list[dict] = []

    progress = tqdm(
        products,
        desc="Products processed",
        unit="product",
        ncols=72,
        bar_format="{desc}: {bar} {n_fmt}/{total_fmt}",
    )

    for product in progress:
        title       = product["title"]
        image_urls  = product["images"]
        safe_name   = sanitize_folder_name(title)
        folder      = output_root / safe_name

        progress.set_postfix_str(safe_name[:30], refresh=True)

        if not image_urls:
            logger.info("No images in API data for: %s", title)
            report_rows.append({"Product Name": title, "Images Downloaded": 0})
            continue

        count = download_images(image_urls, folder)
        report_rows.append({"Product Name": title, "Images Downloaded": count})
        logger.info("'%s' — %d image(s) saved", title, count)

    # ------------------------------------------------------------------
    # Step 3 — CSV report
    # ------------------------------------------------------------------
    report_path = output_root / config.REPORT_FILENAME
    _write_csv_report(report_rows, report_path)

    elapsed = time.time() - start_time
    total_images = sum(r["Images Downloaded"] for r in report_rows)

    print(f"\n🎉  Done in {elapsed:.1f}s")
    print(f"    Products processed : {len(report_rows)}")
    print(f"    Images saved       : {total_images}")
    print(f"    Report             : {report_path}")
    print(f"    Output folder      : {output_root.resolve()}\n")


# ---------------------------------------------------------------------------
# CSV report
# ---------------------------------------------------------------------------

def _write_csv_report(rows: list[dict], path: Path) -> None:
    """Write the download summary to a CSV file at *path*."""
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Product Name", "Images Downloaded"])
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
