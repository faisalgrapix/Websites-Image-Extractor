"""
config.py
---------
Central configuration for the Website Image Downloader.
Edit this file to point the crawler at a different website or tune behaviour.
"""

# ---------------------------------------------------------------------------
# Core settings — change these before running
# ---------------------------------------------------------------------------

# The page the crawler starts from.
# For paginated sites, point this at the first listing / category page.
START_URL: str = "https://www.worldofbooks.com"

# Root folder where all downloaded images are saved.
OUTPUT_FOLDER: str = "output"

# ---------------------------------------------------------------------------
# Image settings
# ---------------------------------------------------------------------------

# Output image format — "jpg" or "webp".
OUTPUT_FORMAT: str = "jpg"

# JPEG encoding quality (0–100). 90 gives excellent quality with reasonable
# file sizes. Ignored when OUTPUT_FORMAT is "webp".
JPG_QUALITY: int = 90

# WebP encoding quality (0–100). Used only when OUTPUT_FORMAT is "webp".
WEBP_QUALITY: int = 90

# Minimum pixel dimension (width OR height) an image must have to be saved.
# Filters out tiny icons, tracking pixels, and decorative spacers.
MIN_IMAGE_SIZE_PX: int = 100

# ---------------------------------------------------------------------------
# Network / concurrency settings
# ---------------------------------------------------------------------------

# Maximum number of parallel image-download threads.
# Keep this low (2–4) to be polite to the target server.
MAX_THREADS: int = 4

# Seconds to wait between page requests so we don't hammer the server.
CRAWL_DELAY_SECONDS: float = 3.0

# How many times to retry a failed image download before giving up.
MAX_RETRIES: int = 5

# Seconds to wait between retry attempts.
RETRY_DELAY_SECONDS: float = 2.0

# HTTP request timeout in seconds.
REQUEST_TIMEOUT: int = 20

# ---------------------------------------------------------------------------
# Browser / Playwright settings
# ---------------------------------------------------------------------------

# Run Playwright in headless mode (True = no visible browser window).
HEADLESS: bool = True

# Extra milliseconds to wait after a page loads before scraping.
# Increase this on JS-heavy sites to let lazy-loaded images appear.
PAGE_LOAD_WAIT_MS: int = 500

# ---------------------------------------------------------------------------
# Filtering — images to IGNORE
# ---------------------------------------------------------------------------

# URL fragments that identify non-product images.
# Any image whose URL contains one of these strings is skipped.
IGNORE_URL_PATTERNS: list[str] = [
    "logo",
    "icon",
    "avatar",
    "spinner",
    "loading",
    "placeholder",
    "pixel",
    "tracking",
    "social",
    "facebook",
    "twitter",
    "instagram",
    "youtube",
    "whatsapp",
    "banner-ad",
    "advertisement",
]

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# Path (relative to OUTPUT_FOLDER) for the CSV summary report.
REPORT_FILENAME: str = "download_report.csv"
