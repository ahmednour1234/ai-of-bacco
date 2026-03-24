"""
app/utils/slugify.py
--------------------
Thin wrapper around python-slugify for consistent slug generation.
"""

from slugify import slugify as _slugify


def generate_slug(text: str, separator: str = "-") -> str:
    """Return a URL-safe slug from arbitrary text."""
    return _slugify(text, separator=separator)
