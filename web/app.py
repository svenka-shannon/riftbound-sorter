"""
Flask web UI for Riftbound Card Sorter.
Runs on port 5000 — access at http://raspberrypi.local:5000

Routes:
  /           → Dashboard (live stats)
  /inventory  → Full card inventory table
  /rules      → Rules editor (view + edit rules.json)
  /export     → Download inventory CSV
  /api/stats  → JSON stats (for live updates)
"""

from flask import Flask, render_template_string, jsonify, request, send_file
from pathlib import Path
import json

from api import inventory
from sorter.rules_engine import RulesEngine

RULES_FILE = Path("config/rules.json")

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Riftbound Card Sorter</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }
    h1 { color: #58a6ff; margin-bottom: 4px; }
    nav a { color: #58a6ff; margin-right: 16px; text-decoration: none; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 24px; min-width: 140px; }
    .card .num { font-size: 2.5em; font-weight: bold; color: #58a6ff; }
    .card .lbl { font-size: 0.85em; color: #8b949e; }
    table { border-collapse: collapse; width: 100%; background: #161b22; border-radius: 8px; overflow: hidden; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; }
    th { background: #1c2128; color: #8b949e; font-size: 0.85em; text-transform: uppercase; }
    tr:hover { background: #1c2128; }
    .badge { background: #1f6feb; color: white; border-radius: 12px; padding: 2px 10px; font-size: 0.8em; }
  </style>
</head>
<body>
  <h1>🃏 Riftbound Card Sorter</h1>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/inventory">Inventory</a>
    <a href="/rules">Rules</a>
    <a href="/export">Export CSV</a>
  </nav>
  <div class="cards" id="stats-cards">
    <div class="card"><div class="num" id="total">–</div><div class="lbl">Cards Sorted</div></div>
    <div class="card"><div class="num" id="unique">–</div><div class="lbl">Unique Cards</div></div>
    <div class="card"><div class="num" id="bins">–</div><div class="lbl">Active Bins</div></div>
  </div>
  <h2>Bin Activity</h2>
  <table id="bin-table"><thead><tr><th>Bin</th><th>Cards</th></tr></thead><tbody></tbody></table>
  <script>
    async function refresh() {
      const r = await fetch('/api/stats');
      const d = await r.json();
      document.getElementById('total').textContent = d.total_scanned;
      document.getElementById('unique').textContent = d.unique_cards;
      document.getElementById('bins').textContent = Object.keys(d.by_bin).length;
      const tb = document.querySelector('#bin-table tbody');
      tb.innerHTML = Object.entries(d.by_bin).map(([b,n]) =>
        `<tr><td><span class="badge">Bin ${b}</span></td><td>${n}</td></tr>`
      ).join('');
    }
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>"""


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def dashboard():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/stats")
    def api_stats():
        return jsonify(inventory.get_session_stats())

    @app.route("/inventory")
    def inv_page():
        rows = inventory.get_inventory(limit=1000)
        rows_html = "".join(
            f"<tr><td>{r['card_id']}</td><td>{r['card_name']}</td><td>{r['count']}</td></tr>"
            for r in rows
        )
        return f"""<html><body style="font-family:system-ui;background:#0d1117;color:#e6edf3;padding:20px">
        <h1 style="color:#58a6ff">Inventory ({len(rows)} cards)</h1>
        <a href="/" style="color:#58a6ff">← Back</a>&nbsp;&nbsp;
        <a href="/export" style="color:#58a6ff">Export CSV</a>
        <table border=1 style="width:100%;border-collapse:collapse;margin-top:16px;background:#161b22">
          <thead><tr style="background:#1c2128"><th>ID</th><th>Name</th><th>Count</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table></body></html>"""

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
        return f"""<html><body style="font-family:monospace;background:#0d1117;color:#e6edf3;padding:20px">
        <h1 style="color:#58a6ff">Rules Editor</h1>
        <a href="/" style="color:#58a6ff">← Back</a>{msg}
        <form method="POST">
          <textarea name="rules_json" rows="30" style="width:100%;background:#161b22;color:#e6edf3;
            border:1px solid #30363d;padding:12px;font-family:monospace;font-size:13px"
          >{current}</textarea><br>
          <button type="submit" style="background:#1f6feb;color:white;border:none;padding:8px 20px;
            border-radius:6px;cursor:pointer;margin-top:8px">Save Rules</button>
        </form></body></html>"""

    @app.route("/export")
    def export():
        path = inventory.export_csv("/tmp/inventory_export.csv")
        return send_file(path, as_attachment=True, download_name="riftbound_inventory.csv")

    return app
