"""
Card identification via perceptual hashing.

Flow:
  1. On first run, build hash database from Riftcodex card images
  2. For each captured card JPEG: compute phash, find nearest match in DB
  3. Return (riftbound_id, confidence) — confidence = 1.0 - (hamming_dist / max_dist)

Requires: imagehash, Pillow
Hash DB stored at data/hash_db.json (project-relative, persistent across reboots)

Confidence threshold tuning guide
-----------------------------------
MAX_DIST = HASH_SIZE * HASH_SIZE = 256 bits (for a 16×16 pHash).

The confidence formula is: confidence = 1.0 - (hamming_distance / 256)

Empirical distance ranges (16×16 pHash on card art):
  0–20   → near-certain match (same card, minor JPEG artefacts / lighting)
  21–50  → probable match (different print quality, slight crop difference)
  51–100 → borderline (different edition, art variant, or partial obstruction)
  >100   → likely a non-match or completely different card

Corresponding confidence values:
  distance 20  → confidence ≥ 0.922   (recommended minimum for production)
  distance 50  → confidence ≥ 0.805
  distance 64  → confidence = 0.750   ← current MIN_CONF lower bound
  distance 100 → confidence = 0.609

Recommended MIN_CONF settings:
  0.90  → strict  — only near-certain matches (distance ≤ 25); lowest false-positive rate
  0.80  → normal  — good matches (distance ≤ 51); balanced precision/recall  ← recommended
  0.75  → loose   — includes borderline matches (distance ≤ 64); may produce false positives

Fallback hash methods:
  If phash confidence < MIN_CONF, ahash and dhash are tried automatically.
  ahash (average hash) — fast, robust to brightness changes.
  dhash (difference hash) — robust to contrast/gamma shifts.
  The method with the highest confidence across all three is returned.

To retune, collect a labelled sample of matched/unmatched card images, record
the hamming distances, and pick MIN_CONF so that recall on true matches is ≥95%
while false-positive rate stays below your target.
"""

import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
import imagehash

HASH_DB_FILE = Path(__file__).parent.parent / "data" / "hash_db.json"
HASH_SIZE    = 16      # pHash/ahash/dhash size (16×16 = 256-bit hash)
MIN_CONF     = 0.80    # below this confidence → reject (unknown card)
                       # See tuning guide above; 0.80 ≈ distance ≤ 51

_hash_db: dict[str, str] = {}          # riftbound_id → hex phash string
_hash_db_ahash: dict[str, str] = {}    # riftbound_id → hex ahash string
_hash_db_dhash: dict[str, str] = {}    # riftbound_id → hex dhash string
_card_names: dict[str, str] = {}       # riftbound_id → display name


def build_hash_db(cards: dict[str, dict], force: bool = False):
    """
    Download card images and compute perceptual hashes (phash, ahash, dhash).
    cards: dict from riftcodex.fetch_all_cards()
    """
    global _hash_db, _hash_db_ahash, _hash_db_dhash, _card_names

    if not force and HASH_DB_FILE.exists():
        stored = json.loads(HASH_DB_FILE.read_text())
        _hash_db       = stored.get("phash", stored)   # backwards-compat: old files are flat
        _hash_db_ahash = stored.get("ahash", {})
        _hash_db_dhash = stored.get("dhash", {})
        _card_names    = stored.get("names", {})
        print(f"[identify] Loaded {len(_hash_db)} hashes from {HASH_DB_FILE}")
        return

    HASH_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"[identify] Building hash DB for {len(cards)} cards...")

    # Collect only cards that have an image URL
    work_items = [(card_id, card["image_url"], card.get("name", ""))
                  for card_id, card in cards.items()
                  if card.get("image_url")]

    def _download_and_hash(card_id: str, img_url: str, name: str):
        with urllib.request.urlopen(img_url, timeout=8) as resp:
            img = Image.open(io.BytesIO(resp.read())).convert("RGB")
        ph = imagehash.phash(img, hash_size=HASH_SIZE)
        ah = imagehash.average_hash(img, hash_size=HASH_SIZE)
        dh = imagehash.dhash(img, hash_size=HASH_SIZE)
        return card_id, str(ph), str(ah), str(dh), name

    errors = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_download_and_hash, cid, url, nm): cid
                   for cid, url, nm in work_items}
        for future in as_completed(futures):
            card_id = futures[future]
            try:
                cid, ph, ah, dh, nm = future.result()
                _hash_db[cid]       = ph
                _hash_db_ahash[cid] = ah
                _hash_db_dhash[cid] = dh
                if nm:
                    _card_names[cid] = nm
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"[identify] Warning: failed to hash {card_id}: {e}")
            completed += 1
            if completed % 50 == 0:
                print(f"[identify] Progress: {completed}/{len(work_items)} cards hashed...")

    HASH_DB_FILE.write_text(json.dumps({
        "phash": _hash_db,
        "ahash": _hash_db_ahash,
        "dhash": _hash_db_dhash,
        "names": _card_names,
    }, indent=2))
    print(f"[identify] Hash DB built: {len(_hash_db)} cards, {errors} errors")


def _best_matches(query_hash, db: dict[str, str], top_n: int = 3) -> list[dict]:
    """
    Return the top_n closest matches from db, sorted by ascending hamming distance.
    Each entry: {"card_id": str, "distance": int, "confidence": float}
    """
    max_dist = HASH_SIZE * HASH_SIZE  # 256 for 16×16
    results = []
    for card_id, hash_str in db.items():
        stored = imagehash.hex_to_hash(hash_str)
        dist = query_hash - stored
        results.append({"card_id": card_id, "distance": dist,
                         "confidence": 1.0 - dist / max_dist})
    results.sort(key=lambda x: x["distance"])
    return results[:top_n]


def identify_with_details(jpeg_bytes: bytes) -> dict:
    """
    Identify a card from JPEG bytes, with full debugging information.

    Returns a dict:
      {
        "card_id":        str | None,   # riftbound_id, or None if below threshold
        "card_name":      str | None,   # display name if known
        "confidence":     float,        # 0.0–1.0
        "hamming_distance": int,
        "method":         str,          # "phash", "ahash", or "dhash"
        "top3": [                       # top 3 candidates for the winning method
          {"card_id": str, "confidence": float, "distance": int},
          ...
        ]
      }

    Identification strategy:
      1. Try phash; if confidence ≥ MIN_CONF, return result.
      2. If phash fails threshold, try ahash and dhash.
      3. Return the method with the highest confidence across all three.
    """
    if not _hash_db:
        raise RuntimeError("Hash DB not loaded. Call build_hash_db() first.")

    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")

    candidates: list[dict] = []  # each: {method, top_match, top3}

    # --- phash ---
    ph = imagehash.phash(img, hash_size=HASH_SIZE)
    ph_top = _best_matches(ph, _hash_db)
    if ph_top:
        candidates.append({"method": "phash", "top_match": ph_top[0], "top3": ph_top})

    # --- fallback: ahash and dhash if phash confidence is below threshold ---
    if not candidates or candidates[0]["top_match"]["confidence"] < MIN_CONF:
        if _hash_db_ahash:
            ah = imagehash.average_hash(img, hash_size=HASH_SIZE)
            ah_top = _best_matches(ah, _hash_db_ahash)
            if ah_top:
                candidates.append({"method": "ahash", "top_match": ah_top[0], "top3": ah_top})

        if _hash_db_dhash:
            dh = imagehash.dhash(img, hash_size=HASH_SIZE)
            dh_top = _best_matches(dh, _hash_db_dhash)
            if dh_top:
                candidates.append({"method": "dhash", "top_match": dh_top[0], "top3": dh_top})

    if not candidates:
        return {"card_id": None, "card_name": None, "confidence": 0.0,
                "hamming_distance": HASH_SIZE * HASH_SIZE, "method": "phash", "top3": []}

    # Pick the candidate with the highest confidence
    best = max(candidates, key=lambda c: c["top_match"]["confidence"])
    top  = best["top_match"]
    conf = top["confidence"]
    cid  = top["card_id"] if conf >= MIN_CONF else None

    return {
        "card_id":          cid,
        "card_name":        _card_names.get(cid) if cid else None,
        "confidence":       conf,
        "hamming_distance": top["distance"],
        "method":           best["method"],
        "top3":             best["top3"],
    }


def identify(jpeg_bytes: bytes) -> tuple[str | None, float]:
    """
    Identify a card from JPEG bytes.
    Returns (riftbound_id, confidence) or (None, confidence) if below threshold.

    Wraps identify_with_details() for backwards compatibility.
    """
    result = identify_with_details(jpeg_bytes)
    return result["card_id"], result["confidence"]
