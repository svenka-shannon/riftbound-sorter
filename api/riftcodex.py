"""
Riftcodex API client — unofficial Riftbound card database.
No authentication required.
Docs: https://riftcodex.com/docs/riftcodex/schemas/card

Card object fields:
  riftbound_id, name, type, rarity, domain, cost,
  attack, health, speed, attributes, tcgplayer_id, image_url
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL   = "https://riftcodex.com/api/v1"
CACHE_FILE = Path(__file__).parent.parent / "data" / "cards.json"
CACHE_TTL  = 86400  # 24 hours: refresh from the API after this, but keep using a
                    # stale cache whenever the API cannot be reached

_card_cache: dict[str, dict] = {}   # riftbound_id → card data
_last_fetch: float = 0


class CardDataUnavailable(RuntimeError):
    """The API is unreachable and there is no local card cache at all."""


def _fetch(endpoint: str) -> dict | list:
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _read_cache_file() -> dict | None:
    """The cached cards, or None if missing / unreadable / empty."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError) as exc:
        print(f"[riftcodex] Warning: card cache {CACHE_FILE} unreadable: {exc}")
        return None
    return data if isinstance(data, dict) and data else None


def _write_cache_file(cards: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_name(f".{CACHE_FILE.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cards, indent=2))
    os.replace(tmp, CACHE_FILE)


def fetch_all_cards(force: bool = False) -> dict[str, dict]:
    """
    Fetch (or load from cache) all Riftbound cards.
    Returns dict keyed by riftbound_id.

    Network / API failure: falls back to the cache file even if it is older
    than CACHE_TTL (with a warning). Raises CardDataUnavailable only when
    there is no usable cache at all.
    """
    global _card_cache, _last_fetch

    if not force and _card_cache and (time.time() - _last_fetch < CACHE_TTL):
        return _card_cache

    cached = _read_cache_file()
    mtime = CACHE_FILE.stat().st_mtime if cached else 0.0
    if not force and cached and time.time() - mtime < CACHE_TTL:
        _card_cache = cached
        _last_fetch = mtime
        print(f"[riftcodex] Loaded {len(_card_cache)} cards from cache")
        return _card_cache

    print("[riftcodex] Fetching all cards from API...")
    try:
        data = _fetch("cards")
        cards = data if isinstance(data, list) else data.get("cards", [])
        fresh = {c["riftbound_id"]: c for c in cards}
        if not fresh:
            raise ValueError("API returned no cards")
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, KeyError, TypeError,
            AttributeError) as exc:
        if cached:
            age_h = (time.time() - mtime) / 3600
            print(f"[riftcodex] Warning: API unavailable ({exc}); using the cached card list "
                  f"({len(cached)} cards, {age_h:.0f} h old)")
            _card_cache = cached
            _last_fetch = time.time()     # don't hammer the API on every lookup
            return _card_cache
        raise CardDataUnavailable(
            f"cannot reach the Riftcodex API ({exc}) and there is no card cache at {CACHE_FILE}. "
            "Connect the Pi to the internet once (the card list is cached for offline use), "
            "or copy data/cards.json from another install.") from exc

    _card_cache = fresh
    _last_fetch = time.time()
    _write_cache_file(_card_cache)
    print(f"[riftcodex] Cached {len(_card_cache)} cards to {CACHE_FILE}")
    return _card_cache


def get_card(riftbound_id: str) -> dict | None:
    """Lookup a single card by ID (uses local cache first)."""
    if not _card_cache:
        fetch_all_cards()
    return _card_cache.get(riftbound_id)


def get_card_by_name(name: str) -> dict | None:
    """Find card by exact name (case-insensitive)."""
    if not _card_cache:
        fetch_all_cards()
    name_lower = name.lower()
    for card in _card_cache.values():
        if card.get("name", "").lower() == name_lower:
            return card
    return None


def get_image_url(riftbound_id: str) -> str | None:
    card = get_card(riftbound_id)
    return card.get("image_url") if card else None
