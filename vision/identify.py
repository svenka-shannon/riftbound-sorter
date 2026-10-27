"""
Card identification via perceptual hashing.

Flow:
  1. On first run, build hash database from Riftcodex card images
  2. For each captured card JPEG: compute phash, find nearest match in DB
  3. Return (riftbound_id, confidence) — confidence = 1.0 - (hamming_dist / 64)

Requires: imagehash, Pillow
Hash DB stored at data/hash_db.json (project-relative, persistent across reboots)
"""

import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
import imagehash

HASH_DB_FILE = Path(__file__).parent.parent / "data" / "hash_db.json"
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

    # Collect only cards that have an image URL
    work_items = [(card_id, card["image_url"])
                  for card_id, card in cards.items()
                  if card.get("image_url")]

    def _download_and_hash(card_id: str, img_url: str):
        with urllib.request.urlopen(img_url, timeout=8) as resp:
            img = Image.open(io.BytesIO(resp.read())).convert("RGB")
        h = imagehash.phash(img, hash_size=HASH_SIZE)
        return card_id, str(h)

    errors = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_download_and_hash, cid, url): cid
                   for cid, url in work_items}
        for future in as_completed(futures):
            card_id = futures[future]
            try:
                cid, hash_str = future.result()
                _hash_db[cid] = hash_str
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"[identify] Warning: failed to hash {card_id}: {e}")
            completed += 1
            if completed % 50 == 0:
                print(f"[identify] Progress: {completed}/{len(work_items)} cards hashed...")

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
