"""
app/utils/file_helpers.py
--------------------------
Utilities for safe file naming, extension extraction, and MIME detection.
"""

import mimetypes
import os
import re
import unicodedata
from pathlib import Path


def safe_filename(filename: str) -> str:
    """Sanitize a filename by removing unsafe characters."""
    # Normalize unicode characters
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")
    # Replace anything that isn't alphanumeric, dot, dash, or underscore
    filename = re.sub(r"[^\w.\-]", "_", filename)
    # Collapse consecutive underscores/dots
    filename = re.sub(r"_+", "_", filename).strip("_")
    return filename or "file"


def get_file_extension(filename: str) -> str:
    """Return the lowercase extension without the dot, e.g. 'pdf'."""
    return Path(filename).suffix.lstrip(".").lower()


def detect_file_type(filename: str, content_type: Optional[str] = None) -> str:
    """
    Return a canonical MIME type string.
    Falls back to mimetypes guessing from the filename if content_type is absent.
    """
    if content_type and content_type != "application/octet-stream":
        return content_type.split(";")[0].strip()
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
