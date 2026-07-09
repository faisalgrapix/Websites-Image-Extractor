"""
downloader.py
-------------
Downloads a list of image URLs into a target folder, converts each image to
the configured output format, and returns a count of successfully saved files.

Features
~~~~~~~~
- Retry logic (up to config.MAX_RETRIES attempts per image).
- Sequential naming: cover.jpg, image-1.jpg, image-2.jpg …
- Cover detection heuristic (URL contains "cover", "main", "hero", etc.).
- Skips images that are too small (icons / tracking pixels).
- Thread-safe: each call operates on its own folder and counter.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

import config
from converter import convert_to_output_format, is_too_small
from utils import get_logger, looks_like_cover, url_to_filename, ensure_directory

logger = get_logger(__name__)

# Shared session for connection pooling across all downloads in a run.
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_images(image_urls: list[str], folder: Path) -> int:
    """
    Download and convert all images in *image_urls* into *folder*.

    Downloads run in a thread pool (size: :data:`config.MAX_THREADS`).
    Each image is:
    1. Downloaded to a temporary file with its original extension.
    2. Checked for minimum size (tiny images are discarded).
    3. Converted to the configured output format.
    4. Renamed sequentially.

    Args:
        image_urls: Ordered list of absolute image URLs to download.
        folder:     Destination directory (created if it does not exist).

    Returns:
        Number of images successfully saved.
    """
    ensure_directory(folder)

    ext = f".{config.OUTPUT_FORMAT.lower()}"

    # Split URLs into cover candidate (first match) + the rest.
    cover_url: str | None = None
    regular_urls: list[str] = []

    for url in image_urls:
        if cover_url is None and looks_like_cover(url):
            cover_url = url
        else:
            regular_urls.append(url)

    # If no explicit cover was found, treat the first image as the cover.
    if cover_url is None and image_urls:
        cover_url = image_urls[0]
        regular_urls = image_urls[1:]

    tasks: list[tuple[str, Path]] = []

    if cover_url:
        tasks.append((cover_url, folder / f"cover{ext}"))

    for idx, url in enumerate(regular_urls, start=1):
        tasks.append((url, folder / f"image-{idx}{ext}"))

    success_count = 0

    with ThreadPoolExecutor(max_workers=config.MAX_THREADS) as executor:
        future_to_dest = {
            executor.submit(_download_and_convert, url, dest): dest
            for url, dest in tasks
        }
        for future in as_completed(future_to_dest):
            dest = future_to_dest[future]
            try:
                saved = future.result()
                if saved:
                    success_count += 1
            except Exception as exc:
                logger.error("Unexpected error saving %s: %s", dest.name, exc)

    return success_count


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_and_convert(url: str, final_dest: Path) -> bool:
    """
    Download *url*, convert to the output format, and save to *final_dest*.

    If *final_dest* already exists the download is skipped (duplicate guard).

    Args:
        url:        Absolute image URL.
        final_dest: Intended final path including the correct extension.

    Returns:
        ``True`` if the image was saved successfully, ``False`` otherwise.
    """
    # Duplicate guard — if the final file already exists, skip.
    if final_dest.exists():
        logger.debug("Already exists, skipping: %s", final_dest.name)
        return False

    # Determine a temporary path using the original file extension.
    original_ext = _original_extension(url)
    tmp_path = final_dest.with_suffix(original_ext + ".tmp")

    raw_bytes = _fetch_with_retry(url)
    if raw_bytes is None:
        return False

    # Write raw bytes to a temp file so Pillow can open it properly.
    try:
        tmp_path.write_bytes(raw_bytes)
    except OSError as exc:
        logger.error("Cannot write temp file %s: %s", tmp_path, exc)
        return False

    # Size filter — discard icons and tracking pixels.
    if is_too_small(tmp_path):
        logger.debug("Image too small, discarding: %s", url)
        tmp_path.unlink(missing_ok=True)
        return False

    # Convert to the configured output format.
    converted = convert_to_output_format(tmp_path)
    if converted is None:
        tmp_path.unlink(missing_ok=True)
        return False

    # Rename the converted file to the desired final name.
    try:
        converted.rename(final_dest)
    except OSError as exc:
        logger.error("Cannot rename %s → %s: %s", converted, final_dest, exc)
        return False

    logger.debug("Saved: %s", final_dest.name)
    return True


def _fetch_with_retry(url: str) -> bytes | None:
    """
    Fetch *url* with up to :data:`config.MAX_RETRIES` attempts.

    Args:
        url: Absolute image URL.

    Returns:
        Raw response bytes, or ``None`` if all attempts fail.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = _session.get(url, timeout=config.REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt, config.MAX_RETRIES, url, exc,
            )
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_DELAY_SECONDS)

    logger.error("All %d attempts failed for: %s", config.MAX_RETRIES, url)
    return None


def _original_extension(url: str) -> str:
    """
    Extract the file extension from *url*, defaulting to ``.jpg``.

    Args:
        url: Absolute image URL.

    Returns:
        Lowercase extension string including the leading dot, e.g. ``.png``.
    """
    path = urlparse(url).path.split("?")[0]
    ext = Path(path).suffix.lower()
    return ext if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"} else ".jpg"
