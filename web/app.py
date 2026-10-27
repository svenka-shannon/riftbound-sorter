"""
Flask web UI for Riftbound Card Sorter.
Runs on port 5000 — access at http://raspberrypi.local:5000

Routes:
  /                  → Dashboard (live stats, sort speed calc, session history)
  /inventory         → Full card inventory table (search + bin filter)
  /rules             → Rules editor (view + edit rules.json)
  /export            → Download inventory CSV
  /export/tcgplayer  → Download TCGPlayer wishlist import CSV
  /api/stats         → JSON stats (for live updates)
  /api/status        → JSON sorter status (cpm, hopper)
  /api/sessions      → JSON last 5 sort sessions
"""

from flask import Flask, render_template_string, jsonify, request, send_file, Response
from pathlib import Path
import csv
import io
import json
import sqlite3
import time

from api import inventory
from sorter.rules_engine import RulesEngine

RULES_FILE = Path("config/rules.json")
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
# HTML templates
# ---------------------------------------------------------------------------

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

  <h2>Bin Activity</h2>
  <table id="bin-table"><thead><tr><th>Bin</th><th>Cards</th></tr></thead><tbody></tbody></table>

  <h2>Recent Sessions</h2>
  <table id="session-table">
    <thead><tr><th>Date</th><th>Cards Sorted</th><th>Duration</th></tr></thead>
    <tbody id="session-tbody"><tr><td colspan="3" class="no-data">Loading…</td></tr></tbody>
  </table>

  <script>
    let currentCpm = 0;

    async function refresh() {
      const r = await fetch('/api/stats');
      const d = await r.json();
      document.getElementById('total').textContent = d.total_scanned;
      document.getElementById('unique').textContent = d.unique_cards;
      document.getElementById('bins').textContent = Object.keys(d.by_bin).length;
      document.getElementById('today').textContent = d.total_today != null ? d.total_today : '–';
      const tb = document.querySelector('#bin-table tbody');
      tb.innerHTML = Object.entries(d.by_bin).map(([b, n]) =>
        '<tr><td><span class="badge">Bin ' + b + '</span></td><td>' + n + '</td></tr>'
      ).join('');
    }

    async function pollStatus() {
      try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const banner = document.getElementById('hopper-banner');
        banner.style.display = d.hopper_empty ? 'block' : 'none';
        currentCpm = parseFloat(d.cards_per_minute) || 0;
        document.getElementById('cpm').textContent = currentCpm;
        updateEstimate();
      } catch(e) {}
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
          '<tr><td>' + s.date + '</td><td>' + s.count + '</td><td>' + s.duration + '</td></tr>'
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
      {{ bin_options|safe }}
    </select>
    <span id="count-label"></span>
  </div>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Count</th><th>Bin</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
  <script>
    const CARDS = {{ cards_json|safe }};

    function applyFilters() {
      const q   = document.getElementById('search').value.toLowerCase();
      const bin = document.getElementById('bin-filter').value;
      const rows = CARDS.filter(function(c) {
        if (q && c.name.toLowerCase().indexOf(q) === -1) return false;
        if (bin && String(c.bin) !== bin) return false;
        return true;
      });
      document.getElementById('tbody').innerHTML = rows.map(function(c) {
        var binCell = c.bin != null
          ? '<span class="badge">Bin ' + c.bin + '</span>'
          : '<span style="color:#8b949e">—</span>';
        return '<tr><td>' + c.id + '</td><td>' + c.name + '</td><td>' + c.count + '</td><td>' + binCell + '</td></tr>';
      }).join('');
      document.getElementById('count-label').textContent =
        'Showing ' + rows.length + ' of ' + CARDS.length;
    }

    applyFilters();
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def dashboard():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/stats")
    def api_stats():
        stats = inventory.get_session_stats()
        try:
            import main as sorter_main
            stats["cards_per_minute"] = sorter_main._status.get("cards_per_minute", 0.0)
            stats["total_today"] = sorter_main._status.get("total_today", 0)
        except Exception:
            stats.setdefault("cards_per_minute", 0.0)
            stats.setdefault("total_today", 0)
        return jsonify(stats)

    @app.route("/api/status")
    def api_status():
        import main as sorter_main
        elapsed = time.time() - sorter_main._session_start
        cpm = round(sorter_main._stats["total"] / elapsed * 60, 1) if elapsed > 0 else 0.0
        return jsonify({
            **sorter_main._status,
            "cards_per_minute": cpm,
            "session_elapsed_s": round(elapsed),
            "total_sorted": sorter_main._stats["total"],
        })

    @app.route("/api/sessions")
    def api_sessions():
        return jsonify(get_session_history(n=5))

    @app.route("/api/throughput")
    def api_throughput():
        import main as sorter_main
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
        bins = get_distinct_bins()
        cards_json = json.dumps([
            {"id": r["card_id"], "name": r["card_name"],
             "count": r["count"], "bin": r["primary_bin"]}
            for r in rows
        ])
        bin_options = "".join(
            f'<option value="{b}">Bin {b}</option>' for b in bins
        )
        return render_template_string(
            INVENTORY_HTML,
            cards_json=cards_json,
            bin_options=bin_options,
        )

    @app.route("/rules", methods=["GET", "POST"])
    def rules_page():
        if request.method == "POST":
            try:
                new_rules = json.loads(request.form["rules_json"])
                RULES_FILE.write_text(json.dumps(new_rules, indent=2))
                msg = "<p style='color:#3fb950'>Rules saved.</p>"
            except Exception as e:
                msg = f"<p style='color:#f85149'>Error: {e}</p>"
        else:
            msg = ""
        current = RULES_FILE.read_text() if RULES_FILE.exists() else "{}"
        return f"""<!DOCTYPE html>
<html>
<head>
  <title>Rules — Riftbound</title>
  <meta charset="utf-8">
  <style>
    body {{ font-family: monospace; background: #0d1117; color: #e6edf3; padding: 20px; }}
    h1 {{ color: #58a6ff; }}
    nav a {{ color: #58a6ff; margin-right: 16px; text-decoration: none; }}
    textarea {{ width: 100%; background: #161b22; color: #e6edf3; border: 1px solid #30363d;
                padding: 12px; font-family: monospace; font-size: 13px; }}
    button {{ background: #1f6feb; color: white; border: none; padding: 8px 20px;
              border-radius: 6px; cursor: pointer; margin-top: 8px; }}
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
  {msg}
  <form method="POST">
    <textarea name="rules_json" rows="30">{current}</textarea><br>
    <button type="submit">Save Rules</button>
  </form>
</body>
</html>"""

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
