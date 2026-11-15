"""
Phone app (PWA) served by web/app.py: the static shell, the camera snapshot
endpoint (web/snapshot.py), pairing (web/pairing.py, `main.py --pair`) and
the token rules around them.
"""

import io
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

os.environ["MOCK_HARDWARE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from PIL import Image

import main
from web import pairing, snapshot

TOKEN = "tok-SECRET-4711"
AUTH = {"X-Auth-Token": TOKEN}
STATIC = ROOT / "web" / "static"


@pytest.fixture
def client():
    from web.app import create_app
    snapshot.reset()
    app = create_app(token=TOKEN)
    app.testing = True
    yield app.test_client()
    snapshot.reset()


def _jpeg(resp) -> Image.Image:
    assert resp.status_code == 200 and resp.mimetype == "image/jpeg"
    img = Image.open(io.BytesIO(resp.data))
    img.load()
    assert img.format == "JPEG"
    return img


# ── static shell ─────────────────────────────────────────────────────────────
def test_app_shell_served_with_pwa_meta(client):
    r = client.get("/")
    assert r.status_code == 200 and r.mimetype == "text/html"
    html = r.get_data(as_text=True)
    for needle in ('rel="manifest" href="/manifest.webmanifest"', 'rel="apple-touch-icon"',
                   'name="apple-mobile-web-app-capable" content="yes"', "viewport-fit=cover",
                   'src="/static/app.js"', 'href="/static/app.css"', 'id="screen-run"',
                   'id="screen-camera"', 'id="screen-setup"'):
        assert needle in html, needle
    assert r.headers["Cache-Control"] == "no-cache"
    for path in ("/static/app.js", "/static/app.css"):
        assert client.get(path).status_code == 200, path


def test_no_external_dependencies():
    """The Pi may be offline: no CDN, no external URL anywhere in the shell."""
    for name in ("app.html", "app.js", "app.css", "sw.js", "manifest.webmanifest"):
        text = (STATIC / name).read_text()
        assert not re.search(r"https?://[\w-]+\.[\w.-]+", text), name


def test_manifest_and_icons(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.mimetype == "application/manifest+json"
    m = json.loads(r.data)
    assert m["display"] == "standalone" and m["scope"] == "/" and m["start_url"].startswith("/")
    purposes = set()
    for icon in m["icons"]:
        ir = client.get(icon["src"])
        assert ir.status_code == 200, icon["src"]
        img = Image.open(io.BytesIO(ir.data))
        assert img.format == "PNG"
        w, h = (int(v) for v in icon["sizes"].split("x"))
        assert img.size == (w, h), icon["src"]
        purposes.add(icon.get("purpose", "any"))
    assert {"any", "maskable"} <= purposes
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    touch = client.get("/apple-touch-icon.png")
    assert touch.status_code == 200 and Image.open(io.BytesIO(touch.data)).size == (180, 180)
    assert Image.open(io.BytesIO(touch.data)).mode == "RGB"      # iOS: no transparency


def test_service_worker_caches_shell_only(client):
    r = client.get("/sw.js")
    assert r.status_code == 200 and "javascript" in r.mimetype
    assert r.headers["Service-Worker-Allowed"] == "/"
    sw = r.get_data(as_text=True)
    shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
    urls = re.findall(r"'([^']+)'", shell)
    assert "/" in urls and "/static/app.js" in urls
    assert not [u for u in urls if u.startswith("/api/")]
    for u in urls:                                    # every precached file exists
        assert client.get(u).status_code == 200, u
    assert "url.pathname.startsWith('/api/')) return" in sw      # API: never from the cache
    assert "req.method !== 'GET') return" in sw


def test_desktop_pages_still_reachable(client):
    d = client.get("/dashboard")
    assert d.status_code == 200 and "Riftbound Card Sorter" in d.get_data(as_text=True)
    for page in ("/dashboard", "/inventory", "/rules"):
        html = client.get(page).get_data(as_text=True)
        assert 'href="/">Phone app</a>' in html and 'href="/dashboard"' in html, page
    app_html = client.get("/").get_data(as_text=True)
    for link in ("/dashboard", "/inventory", "/rules", "/export", "/export/tcgplayer"):
        assert f'href="{link}"' in app_html, link


def test_status_reports_mock_and_run_flag(client):
    d = client.get("/api/status").get_json()
    assert d["mock"] is True and d["run_in_progress"] is False


# ── camera snapshot ──────────────────────────────────────────────────────────
def test_camera_mock_placeholder(client):
    r = client.get("/api/camera.jpg")
    img = _jpeg(r)
    assert img.size == (768, 432)
    assert r.headers["X-Camera-Source"] == "mock"
    assert r.headers["Cache-Control"] == "no-store"


def test_camera_rate_limited_and_single_grab(client, monkeypatch):
    grabs = []
    real = snapshot._grab
    monkeypatch.setattr(snapshot, "_grab", lambda m, c: grabs.append(1) or real(m, c))
    assert client.get("/api/camera.jpg").headers["X-Camera-Source"] == "mock"
    r = client.get("/api/camera.jpg")
    assert r.headers["X-Camera-Source"] == "cached"
    _jpeg(r)
    assert len(grabs) == 1
    monkeypatch.setitem(snapshot._cache, "ts", time.time() - snapshot.MIN_INTERVAL_S - 0.1)
    assert client.get("/api/camera.jpg").headers["X-Camera-Source"] == "mock"
    assert len(grabs) == 2


def test_camera_never_grabs_during_a_run(client, monkeypatch):
    from hardware import camera

    def boom(*a, **k):
        raise AssertionError("camera grabbed during a run")
    monkeypatch.setattr(snapshot, "_grab", boom)
    monkeypatch.setattr(camera, "capture_full_jpeg", boom)
    monkeypatch.setattr(main, "_active_depth", 1)              # starting / running / paused
    monkeypatch.setattr(main, "_last_capture", None)
    r = client.get("/api/camera.jpg")                          # nothing yet: placeholder
    assert r.headers["X-Camera-Source"] == "none"
    _jpeg(r)
    card = io.BytesIO()
    Image.new("RGB", (40, 60), (10, 20, 30)).save(card, format="JPEG")
    monkeypatch.setattr(main, "_last_capture", {"jpeg": card.getvalue(), "ts": time.time() - 3})
    r = client.get("/api/camera.jpg")
    assert r.headers["X-Camera-Source"] == "sorter" and r.data == card.getvalue()
    assert float(r.headers["X-Camera-Age-S"]) >= 2.9


def test_camera_during_run_falls_back_to_last_idle_frame(client, monkeypatch):
    first = client.get("/api/camera.jpg").data                 # idle grab (mock)
    monkeypatch.setattr(main, "_active_depth", 1)
    monkeypatch.setattr(main, "_last_capture", None)
    monkeypatch.setattr(snapshot, "_grab", lambda *a: (_ for _ in ()).throw(AssertionError("grab")))
    r = client.get("/api/camera.jpg")
    assert r.headers["X-Camera-Source"] == "cached" and r.data == first


def test_camera_failure_returns_placeholder(client, monkeypatch):
    from hardware import camera
    monkeypatch.setattr(main, "MOCK_HARDWARE", False)

    def stalled():
        raise camera.CameraTimeout("no main frame from the camera within 1.00 s")
    monkeypatch.setattr(camera, "capture_full_jpeg", stalled)
    r = client.get("/api/camera.jpg")
    assert r.headers["X-Camera-Source"] == "none"
    _jpeg(r)


def test_identify_records_the_sorter_capture(monkeypatch):
    monkeypatch.setattr(main, "identify", lambda jpeg: (None, 0.0))
    monkeypatch.setattr(main, "_last_capture", None)
    main._identify(b"jpeg-bytes")
    assert main._last_capture["jpeg"] == b"jpeg-bytes"
    assert time.time() - main._last_capture["ts"] < 5


# ── pairing + token rules ────────────────────────────────────────────────────
def _pair_path():
    return pairing.pair_file(main.WEB_CONFIG_FILE)


def test_cli_pair_prints_code_not_token(capsys):
    tok = main.load_or_create_web_token()
    assert main.cli_pair() == 0
    out = capsys.readouterr().out
    assert tok not in out
    code = re.search(r"Pairing code: (\d{3}) (\d{3})", out)
    assert code
    path = _pair_path()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    raw = path.read_text()
    assert code.group(1) + code.group(2) not in raw and tok not in raw    # stored hashed


def test_pair_flow_single_use(client):
    assert client.post("/api/pair", json={"code": "123456"}).status_code == 401   # none active
    code = pairing.create_code(_pair_path())
    wrong = f"{(int(code) + 1) % 1000000:06d}"
    r = client.post("/api/pair", json={"code": wrong})
    assert r.status_code == 401 and "tries left" in r.get_json()["error"]
    assert TOKEN not in r.get_data(as_text=True)
    r = client.post("/api/pair", json={"code": code[:3] + " " + code[3:]})       # spaces ok
    assert r.status_code == 200 and r.get_json() == {"token": TOKEN}
    assert r.headers["Cache-Control"] == "no-store"
    assert not _pair_path().exists()
    r = client.post("/api/pair", json={"code": code})                          # used up
    assert r.status_code == 401 and TOKEN not in r.get_data(as_text=True)


def test_pair_attempts_limit(client):
    code = pairing.create_code(_pair_path())
    wrong = f"{(int(code) + 7) % 1000000:06d}"
    for _ in range(pairing.PAIR_MAX_ATTEMPTS):
        assert client.post("/api/pair", json={"code": wrong}).status_code == 401
    r = client.post("/api/pair", json={"code": code})                          # invalidated
    assert r.status_code == 401 and TOKEN not in r.get_data(as_text=True)


def test_pair_expired_and_malformed(client):
    code = pairing.create_code(_pair_path(), now=time.time() - pairing.PAIR_TTL_S - 1)
    r = client.post("/api/pair", json={"code": code})
    assert r.status_code == 401 and "expired" in r.get_json()["error"]
    assert not _pair_path().exists()
    assert client.post("/api/pair", json={"code": "12ab"}).status_code == 400
    assert client.post("/api/pair", data={}).status_code == 400
    assert client.get("/api/pair").status_code == 405                          # never over GET


def test_pair_refused_if_code_cannot_be_consumed(client, tmp_path):
    code = pairing.create_code(_pair_path())
    os.chmod(tmp_path, 0o500)                    # the service can't delete the file
    try:
        r = client.post("/api/pair", json={"code": code})
    finally:
        os.chmod(tmp_path, 0o700)
    assert r.status_code == 500 and TOKEN not in r.get_data(as_text=True)


def test_token_never_served_over_get(client):
    pages = ["/", "/dashboard", "/inventory", "/rules", "/api/status", "/api/stats", "/api/bins",
             "/sw.js", "/manifest.webmanifest", "/static/app.js", "/static/app.html",
             "/api/camera.jpg", "/api/sessions", "/api/throughput"]
    for p in pages:
        r = client.get(p)
        assert TOKEN.encode() not in r.data, p


def test_auth_check_and_existing_token_rules(client):
    assert client.post("/api/auth/check").status_code == 401
    assert client.post("/api/auth/check", headers={"X-Auth-Token": "nope"}).status_code == 401
    r = client.post("/api/auth/check", headers=AUTH)
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    assert client.post("/api/pause").status_code == 401           # unchanged: token required
    assert client.post("/api/bins/0/empty").status_code == 401


# ── option B: Setup screen fields + endpoints ───────────────────────────────
@pytest.fixture
def bclient(monkeypatch, tmp_path):
    import sorter_b
    from hardware import b_mock, vacuum
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sorter_b.install(main, monkeypatch.setattr)
    monkeypatch.setattr(main, "_bins", main.BinCounts(tmp_path / "bin_counts.json",
                                                      tmp_path / "bin_limits.json",
                                                      main.B_DEFAULT_BIN_LIMITS))
    monkeypatch.setattr(vacuum, "VENT_PIN", None)
    b_mock.reset(hopper_cards=5)
    main.init_hardware()
    main._set_state("needs_confirm")
    from web.app import create_app
    return create_app(token=TOKEN).test_client()


def test_b_status_has_lift_height_and_interlock(bclient):
    from hardware import b_geometry as geo
    c = bclient
    d = c.get("/api/b/status").get_json()
    assert d["yaw_ok"] is False and d["yaw_block"]
    assert "busy" in d and "position_hint" in d
    r = c.post("/api/b/home", headers=AUTH)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["yaw_ok"] is True
    assert d["lip_z_mm"] == pytest.approx(round(geo.lip_z(geo.TH_FULL), 1))
    d = c.post("/api/b/lift", json={"th": 3.0}, headers=AUTH).get_json()
    assert d["yaw_ok"] is False and "full height" in d["yaw_block"]
    assert d["lip_z_mm"] == pytest.approx(round(geo.lip_z(3.0), 1))
    r = c.post("/api/b/jog", json={"deg": 1}, headers=AUTH)        # interlock → 409 + reason
    assert r.status_code == 409 and r.get_json()["error"]


def test_b_pump_off_needs_rest_or_card_removed(bclient):
    c = bclient
    assert c.post("/api/b/home", headers=AUTH).status_code == 200
    assert c.post("/api/b/pump", json={"on": True}, headers=AUTH).get_json()["pump"] is True
    r = c.post("/api/b/jog", json={"deg": 1}, headers=AUTH)        # yaw refused with the pump on
    assert r.status_code == 409 and "pump" in r.get_json()["error"]
    r = c.post("/api/b/pump", json={"on": False}, headers=AUTH)    # at full lift: not resting
    assert r.status_code == 409 and "card_removed" in r.get_json()["error"]
    r = c.post("/api/b/pump", json={"on": False, "card_removed": True}, headers=AUTH)
    assert r.status_code == 200 and r.get_json()["pump"] is False


def test_b_motor_off_and_declare_position(bclient):
    from hardware import b_calibration as cal
    c = bclient
    assert c.post("/api/b/home", headers=AUTH).status_code == 200
    assert c.post("/api/b/motor-off").status_code == 401           # token
    r = c.post("/api/b/declare-position", headers=AUTH)            # homed: nothing to declare
    assert r.status_code == 409
    d = c.post("/api/b/motor-off", headers=AUTH).get_json()
    assert d["homed"] is False
    r = c.post("/api/b/declare-position", json={}, headers=AUTH)
    assert r.status_code == 200, r.get_json()
    lo, hi = r.get_json()["position_hint"]
    assert lo <= cal.park_yaw() <= hi
    assert c.post("/api/b/declare-position", json={"yaw": 500}, headers=AUTH).status_code == 400


def test_b_cycle_feeds_the_camera_view():
    """sorter_b identifies through main._identify, which keeps the capture for /api/camera.jpg."""
    import inspect
    import sorter_b
    assert "M._identify(jpeg)" in inspect.getsource(sorter_b.sort_one_card)
