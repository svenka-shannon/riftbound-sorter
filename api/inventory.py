"""
Local SQLite inventory — tracks what cards have been scanned and sorted.

Tables:
  scans(id, card_id, card_name, bin, confidence, ts)
  inventory(card_id, card_name, count, last_seen)
"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path("/tmp/riftbound-sorter/data/inventory.db")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id     TEXT,
                card_name   TEXT,
                bin         INTEGER,
                confidence  REAL,
                ts          REAL DEFAULT (unixepoch('now'))
            );
            CREATE TABLE IF NOT EXISTS inventory (
                card_id     TEXT PRIMARY KEY,
                card_name   TEXT,
                count       INTEGER DEFAULT 1,
                last_seen   REAL
            );
            CREATE INDEX IF NOT EXISTS idx_scans_ts ON scans(ts);
            CREATE INDEX IF NOT EXISTS idx_inv_count ON inventory(count DESC);
        """)
    print(f"[inventory] DB initialized at {DB_PATH}")


def record_scan(card_id: str, card_name: str, bin_num: int, confidence: float):
    """Log a single card scan."""
    ts = time.time()
    with _conn() as db:
        db.execute(
            "INSERT INTO scans(card_id, card_name, bin, confidence, ts) VALUES (?,?,?,?,?)",
            (card_id, card_name, bin_num, confidence, ts)
        )
        db.execute("""
            INSERT INTO inventory(card_id, card_name, count, last_seen)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                count = count + 1,
                last_seen = excluded.last_seen,
                card_name = excluded.card_name
        """, (card_id, card_name, ts))


def get_inventory(limit: int = 500) -> list[dict]:
    """Return inventory sorted by count desc."""
    with _conn() as db:
        rows = db.execute(
            "SELECT card_id, card_name, count, last_seen FROM inventory ORDER BY count DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_stats() -> dict:
    """Stats for current session (last 24h)."""
    since = time.time() - 86400
    with _conn() as db:
        total = db.execute("SELECT COUNT(*) FROM scans WHERE ts > ?", (since,)).fetchone()[0]
        bins  = db.execute(
            "SELECT bin, COUNT(*) as n FROM scans WHERE ts > ? GROUP BY bin ORDER BY bin",
            (since,)
        ).fetchall()
        unique = db.execute(
            "SELECT COUNT(DISTINCT card_id) FROM scans WHERE ts > ?", (since,)
        ).fetchone()[0]
    return {
        "total_scanned": total,
        "unique_cards":  unique,
        "by_bin":        {r["bin"]: r["n"] for r in bins},
    }


def export_csv(path: str = "/tmp/inventory_export.csv"):
    """Export full inventory to CSV."""
    import csv
    rows = get_inventory(limit=100000)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["card_id", "card_name", "count", "last_seen"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[inventory] Exported {len(rows)} rows to {path}")
    return path
