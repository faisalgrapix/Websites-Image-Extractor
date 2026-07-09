"""
utils.py
--------
Shared utility helpers used across the project.
"""

import logging
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a consistently configured logger.

    All modules call this function so log output is uniform — timestamped,
    level-prefixed, and written to both the console and a log file.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        A ready-to-use :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when the same logger is retrieved twice.
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — INFO and above only (keeps terminal clean).
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler — DEBUG and above (full detail for post-run review).
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "downloader.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

# Characters that are illegal in directory / file names on Windows, macOS,
# and Linux (we target the most restrictive common subset).
_INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_DOTS_RE = re.compile(r"\.+$")


def sanitize_folder_name(name: str, max_length: int = 80) -> str:
    """
    Convert an arbitrary string into a safe directory name.

    Transformations applied in order:
    1. Strip leading/trailing whitespace.
    2. Replace characters illegal in file names with a hyphen.
    3. Collapse runs of whitespace to a single space.
    4. Strip trailing dots (illegal on Windows).
    5. Truncate to *max_length* characters.
    6. Fall back to ``"untitled"`` if the result is empty.

    Args:
        name:       Raw page title or product name.
        max_length: Maximum number of characters in the returned name.

    Returns:
        A sanitized string safe to use as a directory name.

    Examples:
        >>> sanitize_folder_name("Atomic Habits: An Easy & Proven Way...")
        'Atomic Habits- An Easy & Proven Way...'
    """
    cleaned = name.strip()
    cleaned = _INVALID_CHARS_RE.sub("-", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = _TRAILING_DOTS_RE.sub("", cleaned)
    cleaned = cleaned[:max_length].strip()
    return cleaned or "untitled"


def ensure_directory(path: Path) -> Path:
    """
    Create *path* (and any missing parents) if it does not already exist.

    Args:
        path: Target directory path.

    Returns:
        The same *path* object, for convenient chaining.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def is_svg_url(url: str) -> bool:
    """
    Return ``True`` if *url* looks like an SVG file.

    SVG files are skipped unless the caller explicitly opts in, because most
    SVGs on product sites are logos or icons rather than product imagery.

    Args:
        url: Absolute or relative image URL.

    Returns:
        ``True`` when the URL ends with ``.svg`` (case-insensitive).
    """
    return url.lower().split("?")[0].endswith(".svg")


def url_to_filename(url: str) -> str:
    """
    Extract the bare filename (without query string) from a URL.

    Args:
        url: Image URL, e.g. ``https://example.com/images/cover.jpg?v=3``.

    Returns:
        The filename portion, e.g. ``cover.jpg``.
    """
    path_part = url.split("?")[0].split("#")[0]
    return path_part.rstrip("/").split("/")[-1] or "image"


def looks_like_cover(url: str) -> bool:
    """
    Heuristic: return ``True`` if *url* suggests the image is a cover / hero.

    Any image whose URL contains "cover", "main", "hero", "front", or
    "thumbnail" is treated as the primary product image and saved as
    ``cover.webp`` rather than ``image-N.webp``.

    Args:
        url: Absolute image URL.

    Returns:
        ``True`` when the URL matches a cover-like pattern.
    """
    lower = url.lower()
    cover_signals = ("cover", "main", "hero", "front", "thumbnail", "primary")
    return any(signal in lower for signal in cover_signals)
