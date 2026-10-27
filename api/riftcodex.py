"""
Riftcodex API client — unofficial Riftbound card database.
No authentication required.
Docs: https://riftcodex.com/docs/riftcodex/schemas/card

Card object fields:
  riftbound_id, name, type, rarity, domain, cost,
  attack, health, speed, attributes, tcgplayer_id, image_url
"""

import json
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL   = "https://riftcodex.com/api/v1"
CACHE_FILE = Path(__file__).parent.parent / "data" / "cards.json"
CACHE_TTL  = 86400  # 24 hours

_card_cache: dict[str, dict] = {}   # riftbound_id → card data
_last_fetch: float = 0


def _fetch(endpoint: str) -> dict | list:
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def fetch_all_cards(force: bool = False) -> dict[str, dict]:
    """
    Fetch (or load from cache) all Riftbound cards.
    Returns dict keyed by riftbound_id.
    """
    global _card_cache, _last_fetch

    if not force and _card_cache and (time.time() - _last_fetch < CACHE_TTL):
        return _card_cache

    if not force and CACHE_FILE.exists():
        mtime = CACHE_FILE.stat().st_mtime
        if time.time() - mtime < CACHE_TTL:
            _card_cache = json.loads(CACHE_FILE.read_text())
            _last_fetch = mtime
            print(f"[riftcodex] Loaded {len(_card_cache)} cards from cache")
            return _card_cache

    print("[riftcodex] Fetching all cards from API...")
    data = _fetch("cards")
    cards = data if isinstance(data, list) else data.get("cards", [])
    _card_cache = {c["riftbound_id"]: c for c in cards}
    _last_fetch = time.time()

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(_card_cache, indent=2))
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
