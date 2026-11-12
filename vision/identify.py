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

Ambiguity margin:
  A match is only accepted if the runner-up is clearly worse: its hamming
  distance must exceed the best one by at least MIN_MARGIN_BITS. Two cards
  with similar art (or a near-duplicate entry) otherwise get confused and the
  card is sorted into the wrong bin; with this check it goes to the reject
  bin instead ("when in doubt, reject"). Note that DB entries with IDENTICAL
  art (same hash, different riftbound_id) can never pass the margin and are
  always rejected.
  0 disables the check. Tune together with MIN_CONF from the same labelled
  sample (true-match margins vs. the margins of confusable pairs).

Overrides: config/identify.json  {"min_conf": 0.80, "min_margin_bits": 10,
                                  "fallback": true, "fallback_min_phash_conf": 0.70,
                                  "max_missing_fraction": 0.01}

Fallback hash methods (audit M10):
  pHash decides. An AMBIGUOUS pHash result (confident, but the runner-up is
  within MIN_MARGIN_BITS) is rejected — no weaker hash may override it.
  Only when pHash is merely below MIN_CONF (and unambiguous, and at least
  FALLBACK_MIN_PHASH_CONF) are ahash and dhash consulted, and the card is
  accepted only if ALL THREE agree: pHash's best match, and ahash and dhash
  each confident + unambiguous on that SAME card. Disagreement → reject.
  "fallback": false in config/identify.json turns the fallback off.

Database completeness (audit M10): build_hash_db() returns a report of the
cards it could NOT hash (download failed, or no image URL). A card missing
from the DB is matched against its nearest look-alike instead, so main.py
refuses to sort when more than MAX_MISSING_FRACTION of the card list is
missing ("hash DB incomplete — run main.py --build-db"), and warns loudly
with the count for anything less.

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
CONFIG_FILE  = Path(__file__).parent.parent / "config" / "identify.json"
HASH_SIZE    = 16      # pHash/ahash/dhash size (16×16 = 256-bit hash)
MIN_CONF     = 0.80    # below this confidence → reject (unknown card)
                       # See tuning guide above; 0.80 ≈ distance ≤ 51
MIN_MARGIN_BITS = 10   # runner-up must be ≥ this many bits further away, else reject
FALLBACK = True        # ahash + dhash may confirm a sub-threshold pHash (all must agree)
FALLBACK_MIN_PHASH_CONF = 0.70
MAX_MISSING_FRACTION = 0.01   # > this share of the card list unhashed → refuse to sort
DOWNLOAD_ATTEMPTS = 2


def load_config() -> None:
    """Apply config/identify.json overrides (see module docstring)."""
    global MIN_CONF, MIN_MARGIN_BITS, FALLBACK, FALLBACK_MIN_PHASH_CONF, MAX_MISSING_FRACTION
    if not CONFIG_FILE.exists():
        return
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        if "min_conf" in cfg:
            MIN_CONF = float(cfg["min_conf"])
        if "min_margin_bits" in cfg:
            MIN_MARGIN_BITS = int(cfg["min_margin_bits"])
        if "fallback" in cfg:
            if not isinstance(cfg["fallback"], bool):
                raise ValueError("fallback must be true or false")
            FALLBACK = cfg["fallback"]
        if "fallback_min_phash_conf" in cfg:
            FALLBACK_MIN_PHASH_CONF = float(cfg["fallback_min_phash_conf"])
        if "max_missing_fraction" in cfg:
            MAX_MISSING_FRACTION = float(cfg["max_missing_fraction"])
    except Exception as exc:
        print(f"[identify] Warning: could not read {CONFIG_FILE}: {exc}")


load_config()

_hash_db: dict[str, str] = {}          # riftbound_id → hex phash string
_hash_db_ahash: dict[str, str] = {}    # riftbound_id → hex ahash string
_hash_db_dhash: dict[str, str] = {}    # riftbound_id → hex dhash string
_card_names: dict[str, str] = {}       # riftbound_id → display name


def _hashable(cards: dict[str, dict]) -> dict[str, tuple[str, str]]:
    return {cid: (c["image_url"], c.get("name", "")) for cid, c in cards.items()
            if c.get("image_url")}


def _download_and_hash(card_id: str, img_url: str, name: str):
    last = None
    for _ in range(DOWNLOAD_ATTEMPTS):
        try:
            with urllib.request.urlopen(img_url, timeout=8) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGB")
            break
        except Exception as exc:
            last = exc
    else:
        raise last
    ph = imagehash.phash(img, hash_size=HASH_SIZE)
    ah = imagehash.average_hash(img, hash_size=HASH_SIZE)
    dh = imagehash.dhash(img, hash_size=HASH_SIZE)
    return card_id, str(ph), str(ah), str(dh), name


def build_hash_db(cards: dict[str, dict], force: bool = False, progress=None) -> dict:
    """
    Download card images and compute perceptual hashes (phash, ahash, dhash).
    cards: dict from riftcodex.fetch_all_cards()
    force=False: load data/hash_db.json and only hash the cards it lacks
    (new set, or an earlier failed download). progress(): called after every
    card (main.py feeds the systemd watchdog from it).

    Returns the completeness report (see completeness()); every card that
    could not be hashed is listed and counted, never silently dropped.
    """
    global _hash_db, _hash_db_ahash, _hash_db_dhash, _card_names

    if not force and HASH_DB_FILE.exists():
        stored = json.loads(HASH_DB_FILE.read_text())
        _hash_db       = stored.get("phash", stored)   # backwards-compat: old files are flat
        _hash_db_ahash = stored.get("ahash", {})
        _hash_db_dhash = stored.get("dhash", {})
        _card_names    = stored.get("names", {})
        print(f"[identify] Loaded {len(_hash_db)} hashes from {HASH_DB_FILE}")
    else:
        _hash_db, _hash_db_ahash, _hash_db_dhash, _card_names = {}, {}, {}, {}

    todo = {cid: v for cid, v in _hashable(cards).items()
            if cid not in _hash_db or cid not in _hash_db_ahash or cid not in _hash_db_dhash}
    if todo:
        HASH_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        print(f"[identify] Hashing {len(todo)} of {len(cards)} cards...")
        failed = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {pool.submit(_download_and_hash, cid, url, nm): cid
                       for cid, (url, nm) in todo.items()}
            for future in as_completed(futures):
                card_id = futures[future]
                try:
                    cid, ph, ah, dh, nm = future.result()
                    _hash_db[cid] = ph
                    _hash_db_ahash[cid] = ah
                    _hash_db_dhash[cid] = dh
                    if nm:
                        _card_names[cid] = nm
                except Exception as e:
                    failed[card_id] = repr(e)
                completed += 1
                if progress:
                    progress()
                if completed % 50 == 0:
                    print(f"[identify] Progress: {completed}/{len(todo)} cards hashed...")
        for cid, err in sorted(failed.items()):
            print(f"[identify] FAILED to hash {cid}: {err}")
        tmp = HASH_DB_FILE.with_name(HASH_DB_FILE.name + ".tmp")
        tmp.write_text(json.dumps({
            "phash": _hash_db,
            "ahash": _hash_db_ahash,
            "dhash": _hash_db_dhash,
            "names": _card_names,
        }, indent=2))
        tmp.replace(HASH_DB_FILE)

    report = completeness(cards)
    _print_report(report)
    return report


def completeness(cards: dict[str, dict]) -> dict:
    """{"total", "hashed", "missing": [ids not in the DB], "no_image": [ids
    without an image URL], "missing_fraction", "ok"} for the current card list."""
    total = len(cards)
    missing = sorted(cid for cid in cards
                     if cid not in _hash_db or cid not in _hash_db_ahash or cid not in _hash_db_dhash)
    no_image = sorted(cid for cid in missing if not cards[cid].get("image_url"))
    frac = len(missing) / total if total else 1.0
    return {"total": total, "hashed": total - len(missing), "missing": missing,
            "no_image": no_image, "missing_fraction": frac,
            "ok": total > 0 and frac <= MAX_MISSING_FRACTION}


def _print_report(r: dict) -> None:
    if not r["missing"]:
        print(f"[identify] Hash DB complete: {r['hashed']}/{r['total']} cards")
        return
    bar = "!" * 72
    print(f"[identify] {bar}\n"
          f"[identify] HASH DB INCOMPLETE: {len(r['missing'])} of {r['total']} cards are NOT in the "
          f"database ({r['missing_fraction']:.1%}; {len(r['no_image'])} have no image URL).\n"
          "[identify] Those cards would be matched to a look-alike or rejected.\n"
          f"[identify] Missing: {', '.join(r['missing'])}\n"
          + ("" if r["ok"] else
             f"[identify] More than {MAX_MISSING_FRACTION:.1%} missing — sorting is REFUSED until "
             "`main.py --build-db` completes.\n")
          + f"[identify] {bar}")


def _best_matches(query_hash, db: dict[str, str], top_n: int = 3) -> list[dict]:
    """
    Return the top_n closest matches from db, sorted by ascending hamming distance.
    Each entry: {"card_id": str, "distance": int, "confidence": float}
    """
    max_dist = HASH_SIZE * HASH_SIZE  # 256 for 16×16
    results = []
    for card_id, hash_str in db.items():
        stored = imagehash.hex_to_hash(hash_str)
        dist = int(query_hash - stored)
        results.append({"card_id": card_id, "distance": dist,
                         "confidence": float(1.0 - dist / max_dist)})
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

    Identification strategy (audit M10):
      1. pHash accepted (confidence ≥ MIN_CONF and runner-up ≥ MIN_MARGIN_BITS
         further away) → that card.
      2. pHash ambiguous (confident but margin too small) → REJECT; no other
         hash is consulted.
      3. pHash merely below MIN_CONF (≥ FALLBACK_MIN_PHASH_CONF, unambiguous):
         accepted only if ahash AND dhash are each confident + unambiguous on
         the SAME card as pHash's best match ("method": "phash+ahash+dhash").
      4. Otherwise reject (card_id None).
    """
    if not _hash_db:
        raise RuntimeError("Hash DB not loaded. Call build_hash_db() first.")

    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    max_dist = HASH_SIZE * HASH_SIZE

    def _cand(method, top):
        margin = int(top[1]["distance"] - top[0]["distance"]) if len(top) > 1 else max_dist
        return {"method": method, "top_match": top[0], "top3": top, "margin": margin,
                "confident": top[0]["confidence"] >= MIN_CONF,
                "unambiguous": margin >= MIN_MARGIN_BITS}

    top = _best_matches(imagehash.phash(img, hash_size=HASH_SIZE), _hash_db)
    if not top:
        return {"card_id": None, "card_name": None, "confidence": 0.0,
                "hamming_distance": max_dist, "method": "phash", "top3": [],
                "margin": 0, "ambiguous": False}
    ph = _cand("phash", top)
    cid = None
    method = "phash"
    if ph["confident"] and ph["unambiguous"]:
        cid = ph["top_match"]["card_id"]
    elif (FALLBACK and not ph["confident"] and ph["unambiguous"]
          and ph["top_match"]["confidence"] >= FALLBACK_MIN_PHASH_CONF
          and _hash_db_ahash and _hash_db_dhash):
        others = [_cand("ahash", _best_matches(imagehash.average_hash(img, hash_size=HASH_SIZE),
                                               _hash_db_ahash)),
                  _cand("dhash", _best_matches(imagehash.dhash(img, hash_size=HASH_SIZE),
                                               _hash_db_dhash))]
        want = ph["top_match"]["card_id"]
        if all(o["confident"] and o["unambiguous"] and o["top_match"]["card_id"] == want
               for o in others):
            cid = want
            method = "phash+ahash+dhash"
    t = ph["top_match"]
    return {
        "card_id":          cid,
        "card_name":        _card_names.get(cid) if cid else None,
        "confidence":       t["confidence"],
        "hamming_distance": t["distance"],
        "method":           method,
        "top3":             ph["top3"],
        "margin":           ph["margin"],
        "ambiguous":        bool(ph["confident"] and not ph["unambiguous"]),
    }


def identify(jpeg_bytes: bytes) -> tuple[str | None, float]:
    """
    Identify a card from JPEG bytes.
    Returns (riftbound_id, confidence) or (None, confidence) if below threshold.

    Wraps identify_with_details() for backwards compatibility.
    """
    result = identify_with_details(jpeg_bytes)
    return result["card_id"], result["confidence"]
