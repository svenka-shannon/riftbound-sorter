"""
Card identification via perceptual hashing.

Flow:
  1. On first run, build hash database from Riftcodex card images
  2. For each captured card JPEG: compute phash, find nearest match in DB
  3. Return (riftbound_id, confidence) — confidence = 1.0 - (hamming_dist / 64)

Requires: imagehash, Pillow
Hash DB stored at /tmp/riftbound-sorter/cache/hash_db.json
"""

import io
import json
import urllib.request
from pathlib import Path
from PIL import Image
import imagehash

HASH_DB_FILE = Path("/tmp/riftbound-sorter/cache/hash_db.json")
HASH_SIZE    = 16      # pHash size (16×16 = 256-bit hash)
MIN_CONF     = 0.75    # below this confidence → reject (unknown card)

_hash_db: dict[str, str] = {}   # riftbound_id → hex hash string


def build_hash_db(cards: dict[str, dict], force: bool = False):
    """
    Download card images and compute perceptual hashes.
    cards: dict from riftcodex.fetch_all_cards()
    """
    global _hash_db

    if not force and HASH_DB_FILE.exists():
        _hash_db = json.loads(HASH_DB_FILE.read_text())
        print(f"[identify] Loaded {len(_hash_db)} hashes from {HASH_DB_FILE}")
        return

    HASH_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"[identify] Building hash DB for {len(cards)} cards...")
    errors = 0

    for card_id, card in cards.items():
        img_url = card.get("image_url")
        if not img_url:
            continue
        try:
            with urllib.request.urlopen(img_url, timeout=8) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGB")
            h = imagehash.phash(img, hash_size=HASH_SIZE)
            _hash_db[card_id] = str(h)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"[identify] Warning: failed to hash {card_id}: {e}")

    HASH_DB_FILE.write_text(json.dumps(_hash_db, indent=2))
    print(f"[identify] Hash DB built: {len(_hash_db)} cards, {errors} errors")


def identify(jpeg_bytes: bytes) -> tuple[str | None, float]:
    """
    Identify a card from JPEG bytes.
    Returns (riftbound_id, confidence) or (None, 0.0) if below threshold.
    """
    if not _hash_db:
        raise RuntimeError("Hash DB not loaded. Call build_hash_db() first.")

    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    query_hash = imagehash.phash(img, hash_size=HASH_SIZE)

    best_id   = None
    best_dist = HASH_SIZE * HASH_SIZE  # max possible distance

    for card_id, hash_str in _hash_db.items():
        stored_hash = imagehash.hex_to_hash(hash_str)
        dist = query_hash - stored_hash
        if dist < best_dist:
            best_dist = dist
            best_id   = card_id

    max_dist   = HASH_SIZE * HASH_SIZE
    confidence = 1.0 - (best_dist / max_dist)

    if confidence < MIN_CONF:
        return None, confidence

    return best_id, confidence
