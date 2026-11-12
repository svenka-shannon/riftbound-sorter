"""
Flask web UI for Riftbound Card Sorter.
Runs on port 5000 — access at http://riftbound-sorter.local:5000

Routes:
  /                  → Dashboard (live stats, sort speed calc, session history)
  /inventory         → Full card inventory table (search + bin filter)
  /rules             → Rules editor (view + edit rules.json)
  /export            → Download inventory CSV
  /export/tcgplayer  → Download TCGPlayer wishlist import CSV
  /api/stats         → JSON stats (for live updates)
  /api/status        → JSON sorter status (state, message, cpm, hopper, bin counts)
  /api/bins          → JSON bin counts + capacity limits
  /api/sessions      → JSON last 5 sort sessions

Mutating endpoints (POST) need the shared-secret token (config/web.json,
mode 600, generated on first use). It is never printed to the log / journal:
first run only prints a hint, and `python main.py --web-token` shows it. Send
it in an `X-Auth-Token` header or a `token` form field:
  POST /api/bins/<n>/empty   → reset bin n's count after emptying it
                               (the bin the machine is paused on, or any bin
                               in an idle state — never starting / running)
  POST /api/bins/empty-all   → reset every bin count (idle states only)
  POST /api/pause            → pause at the next card boundary
                               (running / starting / paused)
  POST /api/resume           → resume (paused / stopped / hopper_empty, or
                               cancel a pending pause / stop)
  POST /api/stop             → stop sorting at the next card boundary
                               (running / starting / paused)
  POST /api/confirm-clear    → operator checked the machine after an unclean
                               stop / jam: needs_confirm / jam / error /
                               stopped, and no run in progress (never while
                               paused or starting)
  POST /rules                → validate, save and hot-reload the rules (applied
                               between cards, so any state)
A request refused by the state gate gets 409 with {"error": why}. The gates
are main.can_* — the CLI (--empty-bin, --confirm-clear) goes through these
same endpoints whenever a sorter process is running.
"""

from flask import Flask, render_template_string, jsonify, request, send_file, Response
from functools import wraps
from pathlib import Path
import csv
import io
import json
import os
import sqlite3
import tempfile
import time

from api import inventory
from sorter.rules_engine import RulesEngine

RULES_FILE = Path(__file__).resolve().parent.parent / "config" / "rules.json"
VALID_BINS = set(range(8)) | {9}
MATCH_VALUE_TYPES = (str, int, float, bool)
DB_PATH = Path(__file__).parent.parent / "data/inventory.db"


# ---------------------------------------------------------------------------
# DB helpers (used by new features; core writes still go through api.inventory)
# ---------------------------------------------------------------------------

def _db_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_inventory_with_bins(limit: int = 1000) -> list[dict]:
    """Inventory rows annotated with each card's primary sort bin."""
    try:
        with _db_conn() as db:
            rows = db.execute("""
                SELECT i.card_id, i.card_name, i.count, i.last_seen,
                       (SELECT s.bin FROM scans s WHERE s.card_id = i.card_id
                        GROUP BY s.bin ORDER BY COUNT(*) DESC LIMIT 1) AS primary_bin
                FROM inventory i
                ORDER BY i.count DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_distinct_bins() -> list[int]:
    """Sorted list of distinct bin numbers seen in scans."""
    try:
        with _db_conn() as db:
            rows = db.execute(
                "SELECT DISTINCT bin FROM scans WHERE bin IS NOT NULL ORDER BY bin"
            ).fetchall()
        return [r["bin"] for r in rows]
    except Exception:
        return []


def get_session_history(n: int = 5) -> list[dict]:
    """
    Derive sort sessions from the scans table.
    A gap of >30 min between consecutive scans marks the start of a new session.
    Returns the last n sessions, most recent first.
    """
    GAP = 30 * 60  # seconds
    try:
        with _db_conn() as db:
            rows = db.execute("SELECT ts FROM scans ORDER BY ts ASC").fetchall()
        if not rows:
            return []

        sessions = []
        s_start = rows[0]["ts"]
        s_last  = rows[0]["ts"]
        count   = 1

        for row in rows[1:]:
            ts = row["ts"]
            if ts - s_last > GAP:
                sessions.append({
                    "start": s_start,
                    "end": s_last,
                    "count": count,
                    "duration_s": int(s_last - s_start),
                })
                s_start = ts
                count   = 1
            else:
                count += 1
            s_last = ts

        sessions.append({
            "start": s_start,
            "end": s_last,
            "count": count,
            "duration_s": int(s_last - s_start),
        })

        result = []
        for s in reversed(sessions[-n:]):
            dur = s["duration_s"]
            if dur < 60:
                dur_str = f"{dur}s"
            elif dur < 3600:
                dur_str = f"{dur // 60}m {dur % 60}s"
            else:
                dur_str = f"{dur // 3600}h {(dur % 3600) // 60}m"
            result.append({
                "date":     time.strftime("%Y-%m-%d %H:%M", time.localtime(s["start"])),
                "count":    s["count"],
                "duration": dur_str,
            })
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Rules validation
# ---------------------------------------------------------------------------

def validate_rules(cfg) -> list[str]:
    """Problems with a rules config (empty list = valid). Checked before saving,
    so the running engine never loads something it would misread."""
    errors = []
    if not isinstance(cfg, dict):
        return ["top level must be a JSON object"]
    reject = cfg.get("_reject_bin", 9)
    if not isinstance(reject, int) or isinstance(reject, bool) or reject != 9:
        errors.append("_reject_bin must be 9 (the physical reject bin)")
    bc = cfg.get("_bin_count", 8)
    if not isinstance(bc, int) or isinstance(bc, bool) or not 1 <= bc <= 8:
        errors.append("_bin_count must be an integer 1..8")
    rules = cfg.get("rules")
    if not isinstance(rules, list):
        return errors + ['"rules" must be a list']
    for i, rule in enumerate(rules):
        where = f"rule {i + 1}"
        if not isinstance(rule, dict):
            errors.append(f"{where}: must be an object")
            continue
        if "name" in rule and not isinstance(rule["name"], str):
            errors.append(f"{where}: name must be a string")
        b = rule.get("bin")
        if not isinstance(b, int) or isinstance(b, bool) or b not in VALID_BINS:
            errors.append(f"{where}: bin must be 0-7 or 9 (got {b!r})")
        match = rule.get("match", {})
        if not isinstance(match, dict):
            errors.append(f"{where}: match must be an object")
            continue
        for field, expected in match.items():
            if field == "default":
                if not isinstance(expected, bool):
                    errors.append(f"{where}: match.default must be true/false")
                continue
            vals = expected if isinstance(expected, list) else [expected]
            if isinstance(expected, list) and not expected:
                errors.append(f"{where}: match.{field} is an empty list")
            if not all(isinstance(v, MATCH_VALUE_TYPES) for v in vals):
                errors.append(f"{where}: match.{field} values must be strings / numbers / booleans")
    return errors


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

NAV_AND_TOKEN_JS = """
    function esc(v) {
      return String(v == null ? '' : v).replace(/[&<>"']/g, function(c) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
      });
    }
    function getToken(ask) {
      let t = localStorage.getItem('rbToken');
      if ((!t || ask) ) {
        t = prompt('Web UI token (shown by `python main.py --web-token`):') || '';
        if (t) localStorage.setItem('rbToken', t);
      }
      return t || '';
    }
    async function post(url) {
      let r = await fetch(url, {method: 'POST', headers: {'X-Auth-Token': getToken(false)}});
      if (r.status === 401) {
        r = await fetch(url, {method: 'POST', headers: {'X-Auth-Token': getToken(true)}});
      }
      if (!r.ok) {
        const d = await r.json().catch(function() { return {}; });
        alert(d.error || ('Request failed: ' + r.status));
      }
      return r;
    }
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Riftbound Card Sorter</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
    h1 { color: #58a6ff; margin-bottom: 4px; }
    h2 { color: #e6edf3; margin: 24px 0 10px; font-size: 1.1em; }
    nav a { color: #58a6ff; margin-right: 16px; text-decoration: none; }
    .banner { background: #da3633; color: white; padding: 12px 20px; border-radius: 8px; margin: 12px 0; font-weight: bold; font-size: 1.05em; display: none; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 24px; min-width: 140px; }
    .card .num { font-size: 2.5em; font-weight: bold; color: #58a6ff; }
    .card .lbl { font-size: 0.85em; color: #8b949e; }
    table { border-collapse: collapse; width: 100%; background: #161b22; border-radius: 8px; overflow: hidden; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; }
    th { background: #1c2128; color: #8b949e; font-size: 0.85em; text-transform: uppercase; }
    tr:hover { background: #1c2128; }
    .badge { background: #1f6feb; color: white; border-radius: 12px; padding: 2px 10px; font-size: 0.8em; }
    .speed-box { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 20px; display: inline-flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .speed-box label { color: #8b949e; font-size: 0.9em; }
    .speed-box input { background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 10px; border-radius: 6px; width: 90px; font-size: 1em; }
    .speed-box .result { color: #3fb950; font-weight: bold; font-size: 1.05em; min-width: 120px; }
    .no-data { color: #8b949e; font-size: 0.9em; padding: 12px 0; }
    .empty-btn { background: #1f6feb; color: white; border: none; padding: 4px 12px; border-radius: 6px; cursor: pointer; }
    .full { color: #f85149; font-weight: bold; }
  </style>
</head>
<body>
  <h1>&#x1f0cf; Riftbound Card Sorter</h1>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/inventory">Inventory</a>
    <a href="/rules">Rules</a>
    <a href="/export">Export CSV</a>
    <a href="/export/tcgplayer">Export TCGPlayer</a>
  </nav>
  <div class="banner" id="hopper-banner">&#x26a0;&#xfe0f; Hopper empty — please refill</div>
  <div class="banner" id="state-banner"></div>

  <div style="margin: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
    <span>State: <b id="state">–</b></span>
    <button class="empty-btn" onclick="control('pause')">Pause</button>
    <button class="empty-btn" onclick="control('resume')">Resume</button>
    <button class="empty-btn" onclick="control('stop')">Stop</button>
    <button class="empty-btn" style="background:#da3633" onclick="confirmClear()">Machine clear</button>
  </div>

  <div class="cards" id="stats-cards">
    <div class="card"><div class="num" id="total">–</div><div class="lbl">Cards Sorted</div></div>
    <div class="card"><div class="num" id="unique">–</div><div class="lbl">Unique Cards</div></div>
    <div class="card"><div class="num" id="bins">–</div><div class="lbl">Active Bins</div></div>
    <div class="card"><div class="num" id="cpm">–</div><div class="lbl">Cards / min</div></div>
    <div class="card"><div class="num" id="today">–</div><div class="lbl">Cards Today</div></div>
  </div>

  <div style="margin: 0 0 4px 0">
    <div style="color: #8b949e; font-size: 0.85em; text-transform: uppercase; margin-bottom: 6px;">Throughput — last 60 s</div>
    <div id="sparkline-wrap" style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px;">
      <svg id="sparkline" width="100%" height="48" viewBox="0 0 480 48" preserveAspectRatio="none" style="display:block"></svg>
    </div>
  </div>

  <h2>Sort Speed Estimator</h2>
  <div class="speed-box">
    <label for="card-count">Cards to sort:</label>
    <input type="number" id="card-count" min="1" placeholder="500" oninput="updateEstimate()">
    <span class="result" id="est-time">—</span>
  </div>

  <h2>Bin Capacity</h2>
  <table id="capacity-table">
    <thead><tr><th>Bin</th><th>Cards</th><th>Limit</th><th></th></tr></thead>
    <tbody id="capacity-tbody"></tbody>
  </table>
  <button class="empty-btn" style="margin-top:8px" onclick="emptyAll()">All bins emptied</button>

  <h2>Bin Activity</h2>
  <table id="bin-table"><thead><tr><th>Bin</th><th>Cards</th></tr></thead><tbody></tbody></table>

  <h2>Recent Sessions</h2>
  <table id="session-table">
    <thead><tr><th>Date</th><th>Cards Sorted</th><th>Duration</th></tr></thead>
    <tbody id="session-tbody"><tr><td colspan="3" class="no-data">Loading…</td></tr></tbody>
  </table>

  <script>
    {{ common_js|safe }}
    let currentCpm = 0;

    async function control(what) {
      if (what === 'stop' && !confirm('Stop sorting after the current card?')) return;
      await post('/api/' + what);
      pollStatus();
    }

    async function confirmClear() {
      if (!confirm('Arm, belt and cradle checked and clear (any card removed)? The sorter restarts.')) return;
      await post('/api/confirm-clear');
      pollStatus();
    }

    async function refresh() {
      const r = await fetch('/api/stats');
      const d = await r.json();
      document.getElementById('total').textContent = d.total_scanned;
      document.getElementById('unique').textContent = d.unique_cards;
      document.getElementById('bins').textContent = Object.keys(d.by_bin).length;
      document.getElementById('today').textContent = d.total_today != null ? d.total_today : '–';
      const tb = document.querySelector('#bin-table tbody');
      tb.innerHTML = Object.entries(d.by_bin).map(([b, n]) =>
        '<tr><td><span class="badge">Bin ' + esc(b) + '</span></td><td>' + esc(n) + '</td></tr>'
      ).join('');
    }

    async function pollStatus() {
      try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const banner = document.getElementById('hopper-banner');
        banner.style.display = d.hopper_empty ? 'block' : 'none';
        const sb = document.getElementById('state-banner');
        document.getElementById('state').textContent = d.state +
          (d.pause_requested ? ' (pause requested)' : '') + (d.stop_requested ? ' (stop requested)' : '');
        const alertStates = ['jam', 'paused', 'error', 'needs_confirm'];
        if (alertStates.indexOf(d.state) !== -1 && d.message) {
          sb.textContent = '\u26a0\ufe0f ' + d.state.toUpperCase() + ': ' + d.message;
          sb.style.display = 'block';
        } else {
          sb.style.display = 'none';
        }
        renderCapacity(d.bin_counts || {}, d.bin_limits || {}, d.paused_bin);
        currentCpm = parseFloat(d.cards_per_minute) || 0;
        document.getElementById('cpm').textContent = currentCpm;
        updateEstimate();
      } catch(e) {}
    }

    function renderCapacity(counts, limits, pausedBin) {
      const rows = Object.keys(limits).map(function(b) {
        const n = counts[b] || 0, lim = limits[b];
        const full = n >= lim;
        const label = b === '9' ? 'Bin 9 (reject)' : 'Bin ' + b;
        const bn = parseInt(b, 10);
        return '<tr><td><span class="badge">' + esc(label) + '</span>' +
          (String(pausedBin) === b ? ' <span class="full">waiting</span>' : '') + '</td>' +
          '<td class="' + (full ? 'full' : '') + '">' + esc(n) + '</td><td>' + esc(lim) + '</td>' +
          '<td><button class="empty-btn" onclick="emptyBin(' + bn + ')">Emptied</button></td></tr>';
      });
      document.getElementById('capacity-tbody').innerHTML = rows.join('');
    }

    async function emptyBin(b) {
      if (!confirm('Bin ' + b + ' is physically empty? The sorter resumes if it was waiting on it.')) return;
      await post('/api/bins/' + b + '/empty');
      pollStatus();
    }

    async function emptyAll() {
      if (!confirm('ALL bins are physically empty?')) return;
      await post('/api/bins/empty-all');
      pollStatus();
    }

    function updateEstimate() {
      const n = parseInt(document.getElementById('card-count').value, 10);
      const el = document.getElementById('est-time');
      if (!n || n <= 0 || currentCpm <= 0) { el.textContent = '—'; return; }
      const totalSec = Math.round(n / currentCpm * 60);
      if (totalSec < 60) {
        el.textContent = '~' + totalSec + 's';
      } else if (totalSec < 3600) {
        el.textContent = '~' + Math.floor(totalSec / 60) + 'm ' + (totalSec % 60) + 's';
      } else {
        el.textContent = '~' + Math.floor(totalSec / 3600) + 'h ' + Math.floor((totalSec % 3600) / 60) + 'm';
      }
    }

    async function loadSessions() {
      try {
        const r = await fetch('/api/sessions');
        const sessions = await r.json();
        const tbody = document.getElementById('session-tbody');
        if (!sessions.length) {
          tbody.innerHTML = '<tr><td colspan="3" class="no-data">No sessions recorded yet.</td></tr>';
          return;
        }
        tbody.innerHTML = sessions.map(s =>
          '<tr><td>' + esc(s.date) + '</td><td>' + esc(s.count) + '</td><td>' + esc(s.duration) + '</td></tr>'
        ).join('');
      } catch(e) {
        document.getElementById('session-tbody').innerHTML =
          '<tr><td colspan="3" class="no-data">Unable to load sessions.</td></tr>';
      }
    }

    async function updateSparkline() {
      try {
        const r = await fetch('/api/throughput');
        const d = await r.json();
        const buckets = d.buckets;
        const maxCpm = Math.max(...buckets.map(function(b) { return b.cpm; }), 1);
        const W = 480, H = 48, pad = 3;
        const xs = buckets.map(function(_, i) { return (i / (buckets.length - 1)) * W; });
        const ys = buckets.map(function(b) { return H - pad - (b.cpm / maxCpm) * (H - 2 * pad); });
        const pts = xs.map(function(x, i) { return x.toFixed(1) + ',' + ys[i].toFixed(1); }).join(' ');
        const area = 'M0,' + H + ' ' + xs.map(function(x, i) {
          return 'L' + x.toFixed(1) + ',' + ys[i].toFixed(1);
        }).join(' ') + ' L' + W + ',' + H + ' Z';
        document.getElementById('sparkline').innerHTML =
          '<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">' +
            '<stop offset="0%" stop-color="#58a6ff" stop-opacity="0.25"/>' +
            '<stop offset="100%" stop-color="#58a6ff" stop-opacity="0.02"/>' +
          '</linearGradient></defs>' +
          '<path d="' + area + '" fill="url(#sg)"/>' +
          '<polyline points="' + pts + '" fill="none" stroke="#58a6ff" stroke-width="1.5" stroke-linejoin="round"/>';
      } catch(e) {}
    }

    refresh();
    setInterval(refresh, 3000);
    pollStatus();
    setInterval(pollStatus, 5000);
    updateSparkline();
    setInterval(updateSparkline, 5000);
    loadSessions();
  </script>
</body>
</html>"""


INVENTORY_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Inventory — Riftbound</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
    h1 { color: #58a6ff; margin-bottom: 4px; }
    nav a { color: #58a6ff; margin-right: 16px; text-decoration: none; }
    .controls { display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; align-items: center; }
    input[type=text], select {
      background: #161b22; border: 1px solid #30363d; color: #e6edf3;
      padding: 8px 12px; border-radius: 6px; font-size: 0.95em;
    }
    input[type=text] { min-width: 260px; }
    select { min-width: 140px; }
    table { border-collapse: collapse; width: 100%; background: #161b22; border-radius: 8px; overflow: hidden; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; }
    th { background: #1c2128; color: #8b949e; font-size: 0.85em; text-transform: uppercase; }
    tr:hover { background: #1c2128; }
    .badge { background: #1f6feb; color: white; border-radius: 12px; padding: 2px 10px; font-size: 0.8em; }
    #count-label { color: #8b949e; font-size: 0.9em; }
  </style>
</head>
<body>
  <h1>&#x1f0cf; Inventory</h1>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/inventory">Inventory</a>
    <a href="/rules">Rules</a>
    <a href="/export">Export CSV</a>
    <a href="/export/tcgplayer">Export TCGPlayer</a>
  </nav>
  <div class="controls">
    <input type="text" id="search" placeholder="Search by card name…" oninput="applyFilters()">
    <select id="bin-filter" onchange="applyFilters()">
      <option value="">All bins</option>
      {% for b in bins %}<option value="{{ b }}">Bin {{ b }}</option>{% endfor %}
    </select>
    <span id="count-label"></span>
  </div>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Count</th><th>Bin</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
  <script>
    {{ common_js|safe }}
    const CARDS = {{ cards|tojson }};

    function applyFilters() {
      const q   = document.getElementById('search').value.toLowerCase();
      const bin = document.getElementById('bin-filter').value;
      const rows = CARDS.filter(function(c) {
        if (q && String(c.name || '').toLowerCase().indexOf(q) === -1) return false;
        if (bin && String(c.bin) !== bin) return false;
        return true;
      });
      document.getElementById('tbody').innerHTML = rows.map(function(c) {
        var binCell = c.bin != null
          ? '<span class="badge">Bin ' + esc(c.bin) + '</span>'
          : '<span style="color:#8b949e">—</span>';
        return '<tr><td>' + esc(c.id) + '</td><td>' + esc(c.name) + '</td><td>' + esc(c.count) +
               '</td><td>' + binCell + '</td></tr>';
      }).join('');
      document.getElementById('count-label').textContent =
        'Showing ' + rows.length + ' of ' + CARDS.length;
    }

    applyFilters();
  </script>
</body>
</html>"""


RULES_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Rules — Riftbound</title>
  <meta charset="utf-8">
  <style>
    body { font-family: monospace; background: #0d1117; color: #e6edf3; padding: 20px; }
    h1 { color: #58a6ff; }
    nav a { color: #58a6ff; margin-right: 16px; text-decoration: none; }
    textarea { width: 100%; background: #161b22; color: #e6edf3; border: 1px solid #30363d;
               padding: 12px; font-family: monospace; font-size: 13px; }
    input { background: #161b22; color: #e6edf3; border: 1px solid #30363d; padding: 6px; }
    button { background: #1f6feb; color: white; border: none; padding: 8px 20px;
             border-radius: 6px; cursor: pointer; margin-top: 8px; }
    .ok { color: #3fb950; } .err { color: #f85149; }
  </style>
</head>
<body>
  <h1>&#x1f0cf; Rules Editor</h1>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/inventory">Inventory</a>
    <a href="/rules">Rules</a>
    <a href="/export">Export CSV</a>
    <a href="/export/tcgplayer">Export TCGPlayer</a>
  </nav>
  {% if saved %}<p class="ok">Rules saved; the sorter reloads them before the next card.</p>{% endif %}
  {% if errors %}<div class="err"><p>Not saved:</p><ul>
    {% for e in errors %}<li>{{ e }}</li>{% endfor %}
  </ul></div>{% endif %}
  <form method="POST" onsubmit="document.getElementById('tok').value = document.getElementById('tok').value || getToken(false)">
    <textarea name="rules_json" rows="30">{{ current }}</textarea><br>
    <label>Token <input type="password" name="token" id="tok"></label>
    <button type="submit">Save Rules</button>
  </form>
  <script>
    {{ common_js|safe }}
    document.getElementById('tok').value = localStorage.getItem('rbToken') || '';
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app(token: str | None = None) -> Flask:
    """token: shared secret for the mutating endpoints (default: config/web.json,
    generated on first use)."""
    import main as sorter_main
    app = Flask(__name__)
    app.config["AUTH_TOKEN"] = token or sorter_main.load_or_create_web_token()

    def require_token(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            given = request.headers.get("X-Auth-Token") or request.form.get("token")
            if not sorter_main.check_web_token(given, app.config["AUTH_TOKEN"]):
                return jsonify({"error": "missing or wrong token (python main.py --web-token)"}), 401
            return fn(*a, **k)
        return wrapper

    @app.route("/")
    def dashboard():
        return render_template_string(DASHBOARD_HTML, common_js=NAV_AND_TOKEN_JS)

    @app.route("/api/stats")
    def api_stats():
        stats = inventory.get_session_stats()
        stats["cards_per_minute"] = sorter_main._status.get("cards_per_minute", 0.0)
        stats["total_today"] = sorter_main._status.get("total_today", 0)
        return jsonify(stats)

    @app.route("/api/status")
    def api_status():
        elapsed = time.time() - sorter_main._session_start
        bins = sorter_main._bins.snapshot()
        cpm = round(sorter_main._stats["total"] / elapsed * 60, 1) if elapsed > 0 else 0.0
        return jsonify({
            **sorter_main._status,
            "cards_per_minute": cpm,
            "session_elapsed_s": round(elapsed),
            "total_sorted": sorter_main._stats["total"],
            "stats": dict(sorter_main._stats),
            "bin_counts": bins["counts"],
            "bin_limits": bins["limits"],
            "machine_state": sorter_main.read_machine_state(),
        })

    @app.route("/api/bins")
    def api_bins():
        return jsonify(sorter_main._bins.snapshot())

    @app.route("/api/bins/<int:bin_num>/empty", methods=["POST"])
    @require_token
    def api_bin_empty(bin_num):
        if bin_num not in sorter_main._bins.limits:
            return jsonify({"error": f"unknown bin {bin_num}"}), 400
        ok, why = sorter_main.can_empty_bin(bin_num)
        if not ok:
            return jsonify({"error": why}), 409
        sorter_main.empty_bin(bin_num)
        return jsonify(sorter_main._bins.snapshot())

    @app.route("/api/bins/empty-all", methods=["POST"])
    @require_token
    def api_bins_empty_all():
        ok, why = sorter_main.can_empty_bin(None)
        if not ok:
            return jsonify({"error": why}), 409
        sorter_main.empty_all_bins()
        return jsonify(sorter_main._bins.snapshot())

    def _gated(check, action):
        ok, why = check()
        if not ok:
            return jsonify({"error": why, "state": sorter_main._status.get("state")}), 409
        action()
        return jsonify({"ok": True, "state": sorter_main._status["state"]})

    @app.route("/api/pause", methods=["POST"])
    @require_token
    def api_pause():
        return _gated(sorter_main.can_pause, sorter_main.request_pause)

    @app.route("/api/resume", methods=["POST"])
    @require_token
    def api_resume():
        return _gated(sorter_main.can_resume, sorter_main.request_resume)

    @app.route("/api/stop", methods=["POST"])
    @require_token
    def api_stop():
        return _gated(sorter_main.can_stop, sorter_main.request_stop)

    @app.route("/api/confirm-clear", methods=["POST"])
    @require_token
    def api_confirm_clear():
        return _gated(sorter_main.can_confirm_clear, lambda: sorter_main.confirm_clear("web"))

    @app.route("/api/sessions")
    def api_sessions():
        return jsonify(get_session_history(n=5))

    @app.route("/api/throughput")
    def api_throughput():
        now = time.time()
        scans = list(sorter_main._recent_scans)
        # 12 buckets of 5 s each covering the last 60 s
        buckets = []
        for i in range(12):
            bucket_end = now - (11 - i) * 5
            bucket_start = bucket_end - 5
            count = sum(1 for ts in scans if bucket_start <= ts < bucket_end)
            cpm = round(count * 12, 1)  # 5 s bucket × 12 → per-minute rate
            buckets.append({"t": (i - 11) * 5, "cpm": cpm})
        return jsonify({
            "buckets": buckets,
            "current_cpm": sorter_main._status.get("cards_per_minute", 0.0),
        })

    @app.route("/inventory")
    def inv_page():
        rows = get_inventory_with_bins(limit=1000)
        cards = [{"id": r["card_id"], "name": r["card_name"],
                  "count": r["count"], "bin": r["primary_bin"]} for r in rows]
        bins = [int(b) for b in get_distinct_bins() if b is not None]
        return render_template_string(INVENTORY_HTML, cards=cards, bins=bins,
                                      common_js=NAV_AND_TOKEN_JS)

    @app.route("/rules", methods=["GET"])
    def rules_page():
        current = RULES_FILE.read_text() if RULES_FILE.exists() else "{}"
        return render_template_string(RULES_HTML, current=current, saved=False, errors=[],
                                      common_js=NAV_AND_TOKEN_JS)

    @app.route("/rules", methods=["POST"])
    @require_token
    def rules_save():
        text = request.form.get("rules_json", "")
        try:
            new_rules = json.loads(text)
            errors = validate_rules(new_rules)
        except ValueError as e:
            errors = [f"invalid JSON: {e}"]
        if errors:
            return render_template_string(RULES_HTML, current=text, saved=False, errors=errors,
                                          common_js=NAV_AND_TOKEN_JS), 400
        _write_atomic(RULES_FILE, json.dumps(new_rules, indent=2) + "\n")
        sorter_main.request_rules_reload()
        return render_template_string(RULES_HTML, current=RULES_FILE.read_text(), saved=True,
                                      errors=[], common_js=NAV_AND_TOKEN_JS)

    @app.route("/export")
    def export():
        path = inventory.export_csv("/tmp/inventory_export.csv")
        return send_file(path, as_attachment=True, download_name="riftbound_inventory.csv")

    @app.route("/export/tcgplayer")
    def export_tcgplayer():
        """
        Export inventory in TCGPlayer wishlist import format.
        Columns: Quantity, Name, Set Name, Card Number, Condition, Printing
        """
        rows = inventory.get_inventory(limit=100000)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Quantity", "Name", "Set Name", "Card Number", "Condition", "Printing"])
        for r in rows:
            writer.writerow([
                r["count"],       # Quantity
                r["card_name"],   # Name
                "",               # Set Name (not available)
                r["card_id"],     # Card Number (using card_id as proxy)
                "Near Mint",      # Condition default
                "Normal",         # Printing default
            ])
        output = buf.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=riftbound_tcgplayer.csv"},
        )

    return app
