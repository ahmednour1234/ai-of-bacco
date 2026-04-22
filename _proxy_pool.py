"""
_proxy_pool.py
--------------
Simple rotating proxy pool shared by all scrapers.

Add one proxy per line to proxies.txt in the project root.
Supported formats:
    http://host:port
    http://user:pass@host:port
    socks5://host:port
    socks5://user:pass@host:port

Lines starting with # are ignored.
If proxies.txt is empty or missing, scrapers run without a proxy (direct IP).
"""
import os
import re
import threading

_PROXY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxies.txt")

_lock  = threading.Lock()
_pool: list[str] = []
_idx   = 0


def _load():
    global _pool
    if not os.path.exists(_PROXY_FILE):
        _pool = []
        return
    lines = []
    with open(_PROXY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    _pool = lines


_load()


def reload():
    """Reload proxies.txt at runtime (useful after editing the file)."""
    _load()


def count() -> int:
    return len(_pool)


def has_proxies() -> bool:
    return bool(_pool)


def next_playwright_proxy() -> dict | None:
    """
    Return the next proxy as a Playwright proxy dict, or None if no proxies.
    Format: {"server": "http://host:port", "username": "...", "password": "..."}
    """
    global _idx
    with _lock:
        if not _pool:
            return None
        url = _pool[_idx % len(_pool)]
        _idx += 1

    # Parse optional credentials
    m = re.match(r'((?:https?|socks5)://)([^:@/]+):([^@/]+)@(.+)', url)
    if m:
        return {
            "server":   m.group(1) + m.group(4),
            "username": m.group(2),
            "password": m.group(3),
        }
    return {"server": url}


def next_httpx_proxy() -> str | None:
    """Return the next proxy as a plain URL string for httpx, or None."""
    global _idx
    with _lock:
        if not _pool:
            return None
        url = _pool[_idx % len(_pool)]
        _idx += 1
    return url
