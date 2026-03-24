"""
app/utils/pagination.py
------------------------
Helpers for computing pagination metadata.
"""

import math


def get_total_pages(total: int, per_page: int) -> int:
    """Return the total number of pages given item count and page size."""
    if per_page <= 0:
        return 0
    return math.ceil(total / per_page) if total > 0 else 1


def get_pagination_meta(total: int, page: int, per_page: int) -> dict:
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": get_total_pages(total, per_page),
        "has_next": page < get_total_pages(total, per_page),
        "has_prev": page > 1,
    }
