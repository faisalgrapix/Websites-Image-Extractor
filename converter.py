"""
converter.py
------------
Converts a downloaded image file to the configured output format (JPG by
default) using Pillow, then deletes the original file.

Supported input formats: JPEG, PNG, GIF, BMP, TIFF, WebP, and anything else
Pillow can open.
"""

from pathlib import Path

from PIL import Image, UnidentifiedImageError

import config
from utils import get_logger

logger = get_logger(__name__)

# Map config.OUTPUT_FORMAT values to Pillow save kwargs.
_FORMAT_CONFIG: dict[str, dict] = {
    "jpg": {
        "pillow_format": "JPEG",
        "extension": ".jpg",
        "save_kwargs": {"quality": config.JPG_QUALITY, "optimize": True},
    },
    "webp": {
        "pillow_format": "WEBP",
        "extension": ".webp",
        "save_kwargs": {"quality": config.WEBP_QUALITY, "method": 6},
    },
}


def convert_to_output_format(source_path: Path) -> Path | None:
    """
    Convert *source_path* to the configured output format and delete the original.

    If the source file is already in the target format (e.g. a ``.jpg`` input
    when ``OUTPUT_FORMAT = "jpg"``), no conversion is performed and the
    original path is returned as-is.

    Args:
        source_path: Path to the downloaded image file (any Pillow-supported format).

    Returns:
        Path to the converted output file, or ``None`` if conversion failed.
    """
    fmt_key = config.OUTPUT_FORMAT.lower()
    if fmt_key not in _FORMAT_CONFIG:
        logger.error(
            "Unknown OUTPUT_FORMAT '%s'. Supported: %s",
            config.OUTPUT_FORMAT,
            ", ".join(_FORMAT_CONFIG),
        )
        return None

    fmt = _FORMAT_CONFIG[fmt_key]
    target_path = source_path.with_suffix(fmt["extension"])

    # Nothing to do if the file is already the right format.
    if source_path.suffix.lower() == fmt["extension"]:
        logger.debug("Already %s, skipping conversion: %s", fmt_key.upper(), source_path)
        return source_path

    try:
        with Image.open(source_path) as img:
            # Convert palette / RGBA images to RGB for JPEG compatibility.
            if fmt_key == "jpg" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            img.save(target_path, fmt["pillow_format"], **fmt["save_kwargs"])

        logger.debug("Converted %s → %s", source_path.name, target_path.name)

        # Remove the original only after a successful save.
        source_path.unlink()
        return target_path

    except UnidentifiedImageError:
        logger.warning("Cannot identify image file (possibly corrupt): %s", source_path)
        _safe_delete(source_path)
        return None
    except OSError as exc:
        logger.error("Conversion failed for %s: %s", source_path, exc)
        return None


def is_too_small(source_path: Path) -> bool:
    """
    Return ``True`` if either dimension of the image is below the minimum
    threshold defined in :data:`config.MIN_IMAGE_SIZE_PX`.

    Used to filter out icons, tracking pixels, and decorative spacers before
    conversion.

    Args:
        source_path: Path to the downloaded image file.

    Returns:
        ``True`` when the image is smaller than the minimum size.
    """
    try:
        with Image.open(source_path) as img:
            width, height = img.size
        return width < config.MIN_IMAGE_SIZE_PX or height < config.MIN_IMAGE_SIZE_PX
    except Exception as exc:
        logger.debug("Could not read dimensions of %s: %s", source_path, exc)
        return True  # Treat unreadable files as too small / invalid.


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_delete(path: Path) -> None:
    """Delete *path* without raising if it no longer exists."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("Could not delete %s: %s", path, exc)
