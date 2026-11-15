/*
 * Riftbound Sorter phone app (vanilla JS, no build step, no CDN).
 * Screens: Run (/api/status), Camera (/api/camera.jpg), Setup (/api/b/...).
 * Mutating calls send X-Auth-Token from localStorage "rbToken" (shared with
 * the desktop pages); pairing: POST /api/pair {code} (web/pairing.py).
 * The server is the authority for every gate (409 + reason); the UI only
 * mirrors the gates so buttons that would be refused are disabled.
 */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const TOKEN_KEY = 'rbToken';
  const POLL_MS = 1500;
  const CAM_MS = 1000;
  const RUN_STATES = ['running', 'starting'];
  const CLEAR_STATES = ['needs_confirm', 'jam', 'error'];
  // main.IDLE_STATES: nothing moves, the operator may reach into the bins
  const IDLE_STATES = ['paused', 'stopped', 'jam', 'hopper_empty', 'error', 'idle', 'needs_confirm'];

  const ui = {
    tab: 'run',
    status: null,           // last /api/status
    bstatus: null,          // last /api/b/status (option B)
    online: null,
    nowCpm: null,
    camLive: true,
    camUrl: null,
    busy: false,            // a setup command is in flight
    saveStation: 'hopper',
    liftStep: 0.5,
    probe: null,
  };

  // ── helpers ──────────────────────────────────────────────────────────────
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function fmt(v, digits) {
    if (v == null || Number.isNaN(v)) return '–';
    return Number(v).toFixed(digits);
  }
  function duration(s) {
    s = Math.max(0, Math.round(s || 0));
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  }
  function binLabel(b) { return String(b) === '9' ? 'Reject' : 'Bin ' + b; }
  function stationLabel(n) {
    if (n === 'hopper') return 'Hopper';
    if (n === 'scan') return 'Scan bed';
    if (n === 'reject') return 'Reject';
    if (n === 'park') return 'Park';
    if (n === 'clear') return 'Cam clear';
    const m = /^bin(\d)$/.exec(n);
    return m ? 'Bin ' + m[1] : n;
  }
  const token = () => localStorage.getItem(TOKEN_KEY) || '';

  let toastTimer = null;
  function toast(text, kind) {
    const t = $('toast');
    t.textContent = text;
    t.className = 'toast ' + (kind || '');
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, kind === 'err' || kind === 'warn' ? 7000 : 3000);
  }
  $('toast').addEventListener('click', () => { $('toast').hidden = true; });

  function confirmBox(title, body, okText, kind) {
    return new Promise((resolve) => {
      $('modal-title').textContent = title;
      $('modal-body').textContent = body || '';
      const ok = $('modal-ok');
      ok.textContent = okText || 'OK';
      ok.className = 'btn ' + (kind || 'primary');
      $('modal').hidden = false;
      const done = (v) => {
        $('modal').hidden = true;
        ok.onclick = null; $('modal-cancel').onclick = null;
        resolve(v);
      };
      ok.onclick = () => done(true);
      $('modal-cancel').onclick = () => done(false);
    });
  }

  class Refused extends Error {}

  async function api(path, body) {
    if (!token()) {
      openPair('Pair this phone first: controls need the token.');
      throw new Refused('not paired');
    }
    let r;
    try {
      r = await fetch(path, {
        method: 'POST', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token() },
        body: JSON.stringify(body || {}),
      });
    } catch (e) {
      toast("Can't reach the sorter", 'err');
      throw new Refused('offline');
    }
    const d = await r.json().catch(() => ({}));
    if (r.status === 401) {
      openPair('The sorter rejected this phone’s token. Pair again.');
      throw new Refused('token');
    }
    if (r.status === 409) { toast('Refused: ' + (d.error || 'not now'), 'warn'); throw new Refused(d.error); }
    if (!r.ok) { toast(d.error || ('Failed (' + r.status + ')'), 'err'); throw new Refused(d.error); }
    return d;
  }

  async function getJSON(path) {
    const r = await fetch(path, { cache: 'no-store' });
    if (!r.ok) { const e = new Error(path + ' ' + r.status); e.status = r.status; throw e; }
    return r.json();
  }

  function banner(kind, title, detail, action) {
    const div = document.createElement('div');
    div.className = 'banner ' + kind;
    div.innerHTML = '<div class="bt">' + esc(title) + (detail ? '<small>' + esc(detail) + '</small>' : '') + '</div>';
    if (action) {
      const b = document.createElement('button');
      b.className = 'btn small ' + (action.kind || '');
      b.textContent = action.text;
      b.onclick = action.fn;
      div.appendChild(b);
    }
    return div;
  }
  function setBanners(id, list) {
    const box = $(id);
    box.replaceChildren(...list);
  }

  // ── tabs ─────────────────────────────────────────────────────────────────
  function showTab(name) {
    if (!['run', 'camera', 'setup'].includes(name)) name = 'run';
    ui.tab = name;
    for (const s of ['run', 'camera', 'setup']) $('screen-' + s).hidden = s !== name;
    document.querySelectorAll('.tabs button').forEach((b) => {
      if (b.dataset.tab === name) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
    window.scrollTo(0, 0);
    if (name === 'camera') refreshCamera();
    if (name === 'setup') pollB();
  }
  document.querySelectorAll('.tabs button').forEach((b) => { b.onclick = () => showTab(b.dataset.tab); });
  window.addEventListener('hashchange', () => showTab(location.hash.slice(1)));

  // ── Run screen ───────────────────────────────────────────────────────────
  async function pollStatus() {
    try {
      const d = await getJSON('/api/status');
      ui.status = d;
      setOnline(true);
      renderRun(d);
    } catch (e) {
      setOnline(false);
    }
  }

  async function pollThroughput() {
    if (ui.tab !== 'run') return;
    try {
      const d = await getJSON('/api/throughput');
      // cards counted in the last 60 s = cards / min now
      ui.nowCpm = d.buckets.reduce((a, b) => a + b.cpm, 0) / 12;
      $('st-now').textContent = fmt(ui.nowCpm, ui.nowCpm >= 10 || ui.nowCpm === 0 ? 0 : 1);
    } catch (e) { /* status poll reports the connection */ }
  }

  function setOnline(ok) {
    if (ui.online === ok) return;
    ui.online = ok;
    $('conn').className = 'conn ' + (ok ? 'ok' : 'bad');
    $('conn').setAttribute('aria-label', ok ? 'connected' : 'offline');
    renderGlobalBanners();
  }

  function renderGlobalBanners() {
    const list = [];
    if (ui.online === false) {
      list.push(banner('err', 'Can’t reach the sorter', 'Is the Pi on and on this Wi-Fi? Retrying…'));
    }
    if (!token()) {
      list.push(banner('info', 'Not paired', 'Watching works; controls need pairing.',
        { text: 'Pair', kind: 'primary', fn: () => openPair() }));
    }
    setBanners('global-banners', list);
  }

  function renderRun(d) {
    const state = d.state || 'unknown';
    const badge = $('machine-badge');
    badge.textContent = (d.machine === 'b' ? 'B' : 'v2') + (d.mock ? ' · MOCK' : '');
    badge.className = 'badge' + (d.mock ? ' mock' : '');
    $('menu-about').textContent = 'Machine ' + (d.machine === 'b' ? 'option B' : 'v2') +
      (d.mock ? ' (MOCK hardware)' : '') + '.';

    const pill = $('state-pill');
    pill.textContent = state.replace('_', ' ');
    pill.className = 'pill s-' + state;
    const flags = [];
    if (RUN_STATES.includes(state)) {                 // pending until the card boundary
      if (d.pause_requested) flags.push('pause requested');
      if (d.stop_requested) flags.push('stop requested');
    }
    $('state-flags').textContent = flags.join(' · ');
    $('state-msg').textContent = d.message || '';

    // banners for things the operator must act on
    const bl = [];
    if (state === 'jam') bl.push(banner('err', 'Jam', d.message));
    else if (state === 'error') bl.push(banner('err', 'Error', d.message));
    else if (state === 'needs_confirm') bl.push(banner('warn', 'Check the machine, then tap Machine clear', d.message));
    if (state === 'hopper_empty' || d.hopper_empty) bl.push(banner('warn', 'Hopper empty', 'Refill it, then tap Resume.'));
    if (state === 'paused' && d.paused_bin != null) {
      bl.push(banner('warn', binLabel(d.paused_bin) + ' is full',
        'Empty it, then tap Emptied on ' + binLabel(d.paused_bin) + ': sorting continues.'));
    }
    setBanners('run-banners', bl);
    // the state message is already in a banner for those states
    $('state-msg').hidden = ['jam', 'error', 'needs_confirm'].includes(state);

    // controls (mirror main.can_pause / can_resume / can_stop / can_confirm_clear)
    const pending = d.pause_requested || d.stop_requested;
    const show = {
      start: state === 'stopped',
      resume: state === 'paused' || state === 'hopper_empty' || (RUN_STATES.includes(state) && pending),
      pause: RUN_STATES.includes(state),
      stop: RUN_STATES.includes(state) || state === 'paused',
      clear: CLEAR_STATES.includes(state),
    };
    $('btn-start').hidden = !show.start;
    $('btn-resume').hidden = !show.resume;
    $('btn-resume').textContent = RUN_STATES.includes(state) ? 'Keep running' : 'Resume';
    $('btn-pause').hidden = !show.pause;
    $('btn-pause').disabled = !!d.pause_requested;
    $('btn-stop').hidden = !show.stop;
    $('btn-stop').disabled = !!d.stop_requested;
    $('btn-clear').hidden = !show.clear;
    $('btn-clear').disabled = !!d.run_in_progress;
    let hint = '';
    if (state === 'idle') hint = 'Web-only mode: no sorting loop is running here. Start the sorter service to sort; Setup works.';
    else if (state === 'stopped') hint = 'Start sorts again from the hopper.';
    else if (RUN_STATES.includes(state)) hint = 'Pause and Stop take effect after the card in progress.';
    else if (CLEAR_STATES.includes(state)) hint = 'Machine clear restarts sorting right away.';
    $('controls-hint').textContent = hint;

    // stats
    const st = d.stats || {};
    $('st-avg').textContent = fmt(d.cards_per_minute, 1);
    $('st-total').textContent = st.total != null ? st.total : '–';
    $('st-sorted').textContent = st.sorted != null ? st.sorted : '–';
    $('st-rejects').textContent = st.rejects != null ? st.rejects : '–';
    $('st-today').textContent = st.total_today != null ? st.total_today : '–';
    $('st-doubles').textContent = st.double_picks != null ? st.double_picks : '–';
    $('st-unknowns').textContent = (st.unknowns || 0) + (st.weight_unknown || 0);
    $('st-errors').textContent = (st.errors || 0) + ' · ' + (st.jams || 0);
    $('st-elapsed').textContent = duration(d.session_elapsed_s);
    const lc = d.last_card;
    const parts = [];
    if (lc) {
      parts.push('Last: <b>' + esc(lc.name) + '</b> → ' + esc(binLabel(lc.bin)) +
        (lc.confidence != null ? ' · ' + Math.round(lc.confidence * 100) + '%' : '') +
        (lc.weight_g != null ? ' · ' + esc(lc.weight_g) + ' g' : '') +
        (lc.reason ? ' · ' + esc(lc.reason) : ''));
    }
    if (d.cards_remaining_estimate) parts.push('Hopper: ~' + esc(d.cards_remaining_estimate) + ' cards left');
    $('last-card').innerHTML = parts.join('<br>');

    renderBins(d);
  }

  function renderBins(d) {
    const counts = d.bin_counts || {}, limits = d.bin_limits || {};
    const keys = Object.keys(limits).sort((a, b) => Number(a) - Number(b));
    const idle = IDLE_STATES.includes(d.state);
    const rows = keys.map((b) => {
      const n = counts[b] || 0, lim = limits[b] || 0;
      const frac = lim ? Math.min(1, n / lim) : 0;
      const waiting = d.state === 'paused' && String(d.paused_bin) === b;
      const cls = 'bin' + (n >= lim ? ' full' : frac >= 0.8 ? ' near' : '') + (waiting ? ' waiting' : '');
      const can = idle || waiting;     // main.can_empty_bin: idle states, or the bin it is paused on
      return '<div class="' + cls + '">' +
        '<div class="name"><span>' + esc(binLabel(b)) + (waiting ? '<small>waiting</small>' : '') + '</span>' +
        '<span class="count"><b>' + esc(n) + '</b> / ' + esc(lim) + '</span></div>' +
        '<div class="bar"><i style="width:' + (frac * 100).toFixed(1) + '%"></i></div>' +
        '<button class="btn small" data-empty="' + esc(b) + '"' + (can ? '' : ' disabled') + '>Emptied</button>' +
        '</div>';
    });
    $('bins').innerHTML = rows.join('') || '<p class="hint">No bins reported.</p>';
    $('btn-empty-all').disabled = !idle;            // main.can_empty_bin(None)
  }

  $('bins').addEventListener('click', async (ev) => {
    const b = ev.target.closest('button[data-empty]');
    if (!b || b.disabled) return;
    const n = b.dataset.empty;
    if (!await confirmBox(binLabel(n) + ' emptied?', 'Only tap this once ' + binLabel(n) +
      ' is physically empty. Its count goes back to 0; if the sorter is waiting on it, sorting continues.', 'Emptied')) return;
    await run(b, () => api('/api/bins/' + encodeURIComponent(n) + '/empty'), binLabel(n) + ' count reset');
  });

  $('btn-empty-all').onclick = async (ev) => {
    if (!await confirmBox('All bins emptied?', 'Every bin, including Reject, is physically empty. All counts go back to 0.', 'All emptied')) return;
    await run(ev.currentTarget, () => api('/api/bins/empty-all'), 'All bin counts reset');
  };

  async function run(btn, fn, okText) {
    if (btn) { btn.classList.add('busy'); btn.disabled = true; }
    try {
      const d = await fn();
      if (okText) toast(okText, 'ok');
      return d;
    } catch (e) {
      if (!(e instanceof Refused)) toast(String(e), 'err');
      return null;
    } finally {
      if (btn) { btn.classList.remove('busy'); btn.disabled = false; }
      pollStatus();
    }
  }

  function machineWords() {
    return ui.status && ui.status.machine === 'b'
      ? 'the cup, scan bed and bins' : 'the arm, belt and cradle';
  }

  $('btn-start').onclick = async (ev) => {
    if (!await confirmBox('Start sorting?', 'The machine starts moving. Hands out of ' + machineWords() + '.', 'Start')) return;
    await run(ev.currentTarget, () => api('/api/resume'), 'Starting');
  };
  $('btn-resume').onclick = async (ev) => {
    const s = ui.status ? ui.status.state : '';
    if (!RUN_STATES.includes(s) &&
        !await confirmBox('Resume sorting?', 'The machine starts moving. Hands out of ' + machineWords() + '.', 'Resume')) return;
    await run(ev.currentTarget, () => api('/api/resume'), 'Resuming');
  };
  $('btn-pause').onclick = (ev) => run(ev.currentTarget, () => api('/api/pause'), 'Pausing after this card');
  $('btn-stop').onclick = async (ev) => {
    if (!await confirmBox('Stop sorting?', 'The card in progress is finished, then the machine stops and parks.', 'Stop', 'danger')) return;
    await run(ev.currentTarget, () => api('/api/stop'), 'Stopping after this card');
  };
  $('btn-clear').onclick = async (ev) => {
    if (!await confirmBox('Machine clear?', 'You checked ' + machineWords() +
      ' and removed any stray card. Sorting restarts right away.', 'Machine clear', 'warn')) return;
    await run(ev.currentTarget, () => api('/api/confirm-clear'), 'Confirmed: restarting');
  };

  // ── Camera ───────────────────────────────────────────────────────────────
  const SRC_TEXT = { live: 'live', mock: 'mock', cached: 'cached', sorter: 'sorter’s last capture', none: 'no image' };
  let camBusy = false;
  async function refreshCamera() {
    if (camBusy) return;
    camBusy = true;
    try {
      const r = await fetch('/api/camera.jpg?t=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) throw new Error('camera ' + r.status);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const img = $('cam-img');
      img.onload = () => { if (ui.camUrl && ui.camUrl !== url) URL.revokeObjectURL(ui.camUrl); ui.camUrl = url; };
      img.src = url;
      const src = r.headers.get('X-Camera-Source') || 'none';
      const age = parseFloat(r.headers.get('X-Camera-Age-S') || '0');
      $('cam-src').textContent = SRC_TEXT[src] || src;
      $('cam-src').className = 'pill small src-' + src;
      $('cam-age').textContent = age >= 1 ? duration(age) + ' old' : '';
    } catch (e) {
      $('cam-src').textContent = 'offline';
      $('cam-src').className = 'pill small src-none';
    } finally {
      camBusy = false;
    }
  }
  $('cam-refresh').onclick = refreshCamera;
  $('cam-live').onclick = () => {
    ui.camLive = !ui.camLive;
    $('cam-live').textContent = 'Live: ' + (ui.camLive ? 'on' : 'off');
    $('cam-live').className = 'btn ' + (ui.camLive ? 'primary' : '');
  };

  // ── Setup (option B calibration API) ─────────────────────────────────────
  async function pollB() {
    if (ui.tab !== 'setup') return;
    try {
      const r = await fetch('/api/b/status', { cache: 'no-store' });
      if (r.status === 404) { ui.bstatus = null; renderSetup(null, 'not-b'); return; }
      const d = await r.json();
      if (!r.ok) { renderSetup(null, d.error || ('status ' + r.status)); return; }
      ui.bstatus = d;
      renderSetup(d);
    } catch (e) {
      renderSetup(ui.bstatus, 'offline');
    }
  }

  function yesNo(el, v, yes, no) {
    el.textContent = v == null ? '–' : (v ? yes : no);
    el.className = v == null ? '' : (v ? 'yes' : 'no');
  }

  function renderSetup(d, problem) {
    const bl = [];
    if (problem === 'not-b') {
      bl.push(banner('info', 'Setup is for the option B machine',
        'This sorter is not configured as "machine": "b" (config/machine.json).'));
      setBanners('setup-banners', bl);
      $('setup-body').hidden = true;
      return;
    }
    $('setup-body').hidden = false;
    if (problem === 'offline') bl.push(banner('err', 'Can’t reach the sorter', 'Retrying…'));
    else if (problem) bl.push(banner('err', 'Calibration status failed', problem));
    if (!d) { setBanners('setup-banners', bl); return; }

    const locked = !!d.run_in_progress;
    if (locked) {
      bl.push(banner('warn', 'Sorting is in progress (' + d.state + ')',
        'Calibration is locked while a run is in progress, including paused. Stop the machine on the Run screen first.',
        { text: 'Run', fn: () => showTab('run') }));
    }
    if (d.busy && !locked) bl.push(banner('info', 'The sorter is busy', 'It holds the hardware right now (e.g. parking). Try again in a moment.'));
    if (!d.homed && !locked) bl.push(banner('info', 'Yaw not homed', 'Tap Home before jogging or going to a station.'));
    if (d.sensor_error) bl.push(banner('err', 'Sensor read failed', d.sensor_error));
    setBanners('setup-banners', bl);

    $('rd-yaw').textContent = d.yaw_deg == null ? '–' : fmt(d.yaw_deg, 2) + '°';
    const hint = d.position_hint ? 'hint ' + fmt(d.position_hint[0], 0) + '…' + fmt(d.position_hint[1], 0) + '°' : 'no position hint';
    $('rd-station').textContent = d.station ? 'at ' + stationLabel(d.station)
      : (d.yaw_deg == null ? hint : 'between stations');
    $('rd-th').textContent = d.lift_th == null ? '–' : fmt(d.lift_th, 2) + '°';
    $('rd-lip').textContent = d.lip_z_mm == null ? '' : 'cup lip ' + fmt(d.lip_z_mm, 1) + ' mm';
    yesNo($('rd-homed'), d.homed, 'yes', 'no');
    yesNo($('rd-full'), d.at_full_lift, 'yes', 'no');
    const sw = $('rd-switch');
    sw.textContent = d.home_pressed == null ? '–' : (d.home_pressed ? 'pressed' : 'released');
    sw.className = '';
    const tc = $('rd-touch');
    tc.textContent = d.touch_open == null ? '–' : (d.touch_open ? 'OPEN (touching)' : 'closed');
    tc.className = d.touch_open ? 'no' : (d.touch_open == null ? '' : 'yes');
    const pm = $('rd-pump');
    pm.textContent = d.pump ? 'ON' : 'off';
    pm.className = d.pump ? 'no' : '';
    $('rd-state').textContent = (d.state || '–').replace('_', ' ');

    const yawOk = !!d.yaw_ok && !!d.homed && !d.pump && !d.busy;
    const lock = $('yaw-lock');
    if (locked) { lock.textContent = 'Locked: a run is in progress.'; lock.className = 'lock locked'; }
    else if (yawOk) { lock.textContent = 'Yaw free: lift at full height, cup hanging free.'; lock.className = 'lock ok'; }
    else {
      let why;
      if (d.busy) why = 'the sorter is moving the machine (busy)';
      else if (d.pump) why = 'the pump is on (the cup may hold a card): put it down at a station or take it off, then switch the pump off';
      else if (!d.homed) why = 'not homed (tap Home)';
      else if (!d.at_full_lift) why = 'the lift is not at full height (tap Full lift)';
      else if (d.touch_open) why = 'touch contact OPEN at full lift: the cup rests on something, the slider sticks or the wire is broken';
      else why = d.yaw_block || 'interlock';
      lock.textContent = 'Yaw locked: ' + why;
      lock.className = 'lock locked';
    }

    const stations = d.stations || [];
    renderGoto(stations, d, yawOk && !locked);
    renderSave(stations, d, locked);
    renderCalTable(d);
    setSetupEnabled(d, locked, yawOk);
  }

  function setSetupEnabled(d, locked, yawOk) {
    const off = locked || ui.busy || !!d.busy;      // d.busy: the sorter holds the hardware lock
    $('b-home').disabled = off || !!d.pump;          // homing turns the yaw: refused with the pump on
    $('b-motor-off').disabled = off || !!d.pump;
    $('b-declare').disabled = off || !!d.homed;
    $('park-yaw').textContent = d.calibration && d.calibration.park_yaw != null ? fmt(d.calibration.park_yaw, 1) + '°' : '–';
    $('b-full').disabled = off;
    document.querySelectorAll('.yaw-btn').forEach((b) => { b.disabled = off || !yawOk; });
    document.querySelectorAll('.lift-btn').forEach((b) => { b.disabled = off || d.lift_th == null; });
    $('b-probe').disabled = off || d.lift_th == null;
    $('b-pump-on').disabled = off || !!d.pump;
    $('b-pump-off').disabled = off || !d.pump;
    $('b-servo-raw').disabled = off;
    $('b-save-map').disabled = off;
    $('b-save-park').disabled = off || !d.homed;
    $('b-save-clear').disabled = off || !d.homed;
  }

  function renderGoto(stations, d, enabled) {
    const names = stations.concat(['park', 'clear']);
    const box = $('goto-chips');
    if (box.childElementCount !== names.length) {
      box.innerHTML = names.map((n) => '<button class="chip" data-goto="' + esc(n) + '">' + esc(stationLabel(n)) + '</button>').join('');
    }
    box.querySelectorAll('button').forEach((b) => {
      b.disabled = !enabled || ui.busy || !!d.busy;
      b.classList.toggle('here', d.station === b.dataset.goto);
    });
  }

  const TH_KEYS = { hopper: ['approach_th', 'limit_th', 'floor_th'], scan: ['approach_th', 'limit_th', 'touch_th'] };
  const KEY_TEXT = { approach_th: 'approach', limit_th: 'limit', floor_th: 'floor', touch_th: 'touch' };

  function renderSave(stations, d, locked) {
    const box = $('save-chips');
    if (box.childElementCount !== stations.length) {
      box.innerHTML = stations.map((n) => '<button class="chip" data-save="' + esc(n) + '">' + esc(stationLabel(n)) + '</button>').join('');
    }
    box.querySelectorAll('button').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.save === ui.saveStation));
      b.disabled = locked || ui.busy || !!d.busy;
    });
    const n = ui.saveStation;
    const keys = TH_KEYS[n] || ['approach_th', 'limit_th'];
    const acts = ['<button class="btn primary" data-savekey="yaw"' + (locked || ui.busy || !d.homed ? ' disabled' : '') + '>Yaw ' +
      (d.yaw_deg == null ? '' : fmt(d.yaw_deg, 2) + '° ') + '→ ' + esc(stationLabel(n)) + '</button>'];
    for (const k of keys) {
      acts.push('<button class="btn" data-savekey="' + k + '"' + (locked || ui.busy || d.lift_th == null ? ' disabled' : '') +
        '>th → ' + KEY_TEXT[k] + '</button>');
    }
    $('save-actions').innerHTML = acts.join('');
  }

  function renderCalTable(d) {
    const cal = d.calibration || {};
    const st = cal.stations || {};
    const names = d.stations || Object.keys(st);
    let html = '<thead><tr><th>Station</th><th>yaw</th><th>approach</th><th>limit</th><th>floor / touch</th></tr></thead><tbody>';
    for (const n of names) {
      const s = st[n] || {};
      const extra = s.floor_th != null ? s.floor_th : (s.touch_th != null ? s.touch_th : null);
      html += '<tr class="' + (d.station === n ? 'here' : '') + '"><td>' + esc(stationLabel(n)) + '</td><td>' + fmt(s.yaw, 2) +
        '</td><td>' + fmt(s.approach_th, 2) + '</td><td>' + fmt(s.limit_th, 2) + '</td><td>' +
        (extra == null ? '–' : fmt(extra, 2)) + '</td></tr>';
    }
    $('cal-table').innerHTML = html + '</tbody>';
    const map = cal.servo_map ? cal.servo_map.map((p) => '[' + p.join(', ') + ']').join(' ') : '–';
    $('cal-extra').innerHTML = 'Park yaw <b>' + fmt(cal.park_yaw, 2) + '°</b> · camera-clear yaw <b>' +
      (cal.clear_yaw == null ? 'hopper' : fmt(cal.clear_yaw, 2) + '°') + '</b><br>Servo map ' + esc(map) +
      '<br>Yaw limits ' + esc((d.limits || []).join(' … ')) + '°, lift th ' + esc((d.th_range || []).join(' … ')) + '°';
  }

  async function bcmd(btn, path, body, okText) {
    if (ui.busy) return null;
    ui.busy = true;
    if (ui.bstatus) setSetupEnabled(ui.bstatus, !!ui.bstatus.run_in_progress, false);
    if (btn) btn.classList.add('busy');
    try {
      const d = await api(path, body);
      if (d && d.machine) { ui.bstatus = d; }
      if (okText) toast(typeof okText === 'function' ? okText(d) : okText, 'ok');
      return d;
    } catch (e) {
      if (!(e instanceof Refused)) toast(String(e), 'err');
      return null;
    } finally {
      ui.busy = false;
      if (btn) btn.classList.remove('busy');
      if (ui.bstatus) renderSetup(ui.bstatus);
      pollB();
      pollStatus();
    }
  }

  $('b-home').onclick = async (ev) => {
    if (!await confirmBox('Home the arm?', 'The lift goes to full height, then the arm turns to find the home edge. Keep the swing area clear.', 'Home')) return;
    bcmd(ev.currentTarget, '/api/b/home', {}, 'Homed');
  };
  $('b-full').onclick = (ev) => bcmd(ev.currentTarget, '/api/b/lift/full', {}, 'At full lift');
  document.querySelectorAll('.yaw-btn').forEach((b) => {
    b.onclick = () => bcmd(b, '/api/b/jog', { deg: parseFloat(b.dataset.yaw) },
      (d) => 'Yaw ' + fmt(d.yaw_deg, 2) + '°');
  });
  document.querySelectorAll('#lift-step button').forEach((b) => {
    b.onclick = () => {
      ui.liftStep = parseFloat(b.dataset.step);
      document.querySelectorAll('#lift-step button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
    };
  });
  document.querySelectorAll('.lift-btn').forEach((b) => {
    b.onclick = () => {
      const d = ui.bstatus;
      if (!d || d.lift_th == null) { toast('Lift pose unknown: tap Full lift first', 'warn'); return; }
      const [lo, hi] = d.th_range || [-6, 10];
      const target = Math.round(Math.min(hi, Math.max(lo, d.lift_th + parseInt(b.dataset.dir, 10) * ui.liftStep)) * 1000) / 1000;
      if (target === d.lift_th) { toast('Lift already at its ' + (b.dataset.dir === '1' ? 'top' : 'bottom') + ' limit', 'warn'); return; }
      bcmd(b, '/api/b/lift', { th: target }, (r) => r.touched
        ? 'Stopped on contact at th ' + fmt(r.lift_th, 2) + '° (cup resting on something)'
        : 'Lift th ' + fmt(r.lift_th, 2) + '°');
    };
  });
  $('b-probe').onclick = async (ev) => {
    const d = await bcmd(ev.currentTarget, '/api/b/probe', {});
    if (!d) return;
    $('probe-result').textContent = d.touched
      ? 'Contact opened at th ' + fmt(d.th_touch, 2) + '°. The lift now stands at th ' + fmt(d.lift_th, 2) +
        '° (cup lip ' + fmt(d.lip_z_mm, 1) + ' mm): that is the value a save below stores. Then Full lift.'
      : 'No touch down to the lower limit (th ' + fmt(d.lift_th, 2) + '°).';
    toast(d.touched ? 'Touch at th ' + fmt(d.th_touch, 2) + '°' : 'No touch', d.touched ? 'ok' : 'warn');
  };
  $('b-pump-on').onclick = (ev) => bcmd(ev.currentTarget, '/api/b/pump', { on: true }, 'Pump on (auto-off in 60 s)');
  $('b-pump-off').onclick = async (ev) => {
    const d = ui.bstatus || {};
    const resting = !!d.station && !d.at_full_lift && !!d.touch_open;   // sorter_b._resting_at_station
    if (resting) { bcmd(ev.currentTarget, '/api/b/pump', { on: false }, 'Pump off'); return; }
    const btn = ev.currentTarget;
    if (!await confirmBox('The cup is not resting at a station',
      'The pump only lets go with the cup resting on a station, so a held card is never dropped. ' +
      'Lower the cup onto a station first (Down stops on contact), or take any card off the cup by hand, then confirm.',
      'I removed the card by hand', 'danger')) return;
    bcmd(btn, '/api/b/pump', { on: false, card_removed: true }, 'Pump off');
  };

  $('b-motor-off').onclick = async (ev) => {
    if (!await confirmBox('Yaw motor off?', 'The arm can then be turned by hand. Its saved position is no longer trusted: ' +
      'place it at the park pose and tap "Arm is at park", then Home.', 'Motor off', 'danger')) return;
    bcmd(ev.currentTarget, '/api/b/motor-off', {}, 'Yaw motor off: turn the arm by hand');
  };
  $('b-declare').onclick = async (ev) => {
    const d = ui.bstatus || {};
    const park = d.calibration && d.calibration.park_yaw != null ? fmt(d.calibration.park_yaw, 1) + '°' : 'the park pose';
    if (!await confirmBox('Arm is at park?', 'You placed the arm by hand at ' + park +
      ' (home switch pressed), lift up. The next Home searches only around there.', 'Arm is at park')) return;
    bcmd(ev.currentTarget, '/api/b/declare-position', {}, 'Position declared: now tap Home');
  };

  $('goto-chips').addEventListener('click', async (ev) => {
    const b = ev.target.closest('button[data-goto]');
    if (!b || b.disabled) return;
    bcmd(b, '/api/b/goto', { station: b.dataset.goto }, 'At ' + stationLabel(b.dataset.goto));
  });
  $('save-chips').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-save]');
    if (!b || b.disabled) return;
    ui.saveStation = b.dataset.save;
    if (ui.bstatus) renderSetup(ui.bstatus);
  });
  $('save-actions').addEventListener('click', async (ev) => {
    const b = ev.target.closest('button[data-savekey]');
    if (!b || b.disabled) return;
    const d = ui.bstatus || {};
    const n = ui.saveStation, key = b.dataset.savekey;
    if (key === 'yaw') {
      if (!await confirmBox('Save yaw for ' + stationLabel(n) + '?',
        'Yaw ' + fmt(d.yaw_deg, 3) + '° becomes ' + stationLabel(n) + '’s station angle (config/b_calibration.json).', 'Save')) return;
      bcmd(b, '/api/b/save/station-yaw', { station: n }, 'Saved ' + stationLabel(n) + ' yaw');
    } else {
      if (!await confirmBox('Save ' + KEY_TEXT[key] + ' height for ' + stationLabel(n) + '?',
        'th ' + fmt(d.lift_th, 2) + '° becomes ' + stationLabel(n) + '’s ' + key + '.', 'Save')) return;
      bcmd(b, '/api/b/save/station-th', { station: n, key: key }, 'Saved ' + stationLabel(n) + ' ' + key);
    }
  });
  async function savePose(btn, key, what) {
    const d = ui.bstatus || {};
    if (!await confirmBox('Save ' + what + '?', 'Yaw ' + fmt(d.yaw_deg, 3) + '° becomes the ' + what + ' (' + key + ').', 'Save')) return;
    bcmd(btn, '/api/b/save/pose', { key: key }, 'Saved ' + what);
  }
  $('b-save-park').onclick = (ev) => savePose(ev.currentTarget, 'park_yaw', 'park pose');
  $('b-save-clear').onclick = (ev) => savePose(ev.currentTarget, 'clear_yaw', 'camera-clear pose');
  $('b-servo-raw').onclick = (ev) => {
    const a = parseFloat($('servo-raw').value);
    if (Number.isNaN(a)) { toast('Enter a servo angle', 'warn'); return; }
    bcmd(ev.currentTarget, '/api/b/servo-raw', { angle: a }, 'Servo at ' + a + '°');
  };
  $('b-save-map').onclick = async (ev) => {
    const v = ['sm-th1', 'sm-sv1', 'sm-th2', 'sm-sv2'].map((id) => parseFloat($(id).value));
    if (v.some(Number.isNaN)) { toast('Fill in both [th, servo] points', 'warn'); return; }
    if (!await confirmBox('Save servo map?', '[' + v[0] + ', ' + v[1] + '] and [' + v[2] + ', ' + v[3] + ']', 'Save')) return;
    bcmd(ev.currentTarget, '/api/b/save/servo-map', { points: [[v[0], v[1]], [v[2], v[3]]] }, 'Servo map saved');
  };

  // ── menu + pairing ───────────────────────────────────────────────────────
  function openSheet(id) { $(id).hidden = false; }
  document.querySelectorAll('.sheet').forEach((s) => {
    s.addEventListener('click', (ev) => {
      if (ev.target === s || ev.target.closest('[data-close]')) s.hidden = true;
    });
  });
  $('menu-btn').onclick = () => {
    $('menu-pair').textContent = token() ? 'Paired · manage' : 'Pair this phone';
    openSheet('sheet-menu');
  };
  $('menu-pair').onclick = () => { $('sheet-menu').hidden = true; openPair(); };

  function openPair(why) {
    const paired = !!token();
    $('pair-state').textContent = why || (paired ? 'This phone is paired.' : 'This phone is not paired yet.');
    $('pair-forget').hidden = !paired;
    $('pair-code').value = '';
    openSheet('sheet-pair');
  }

  async function pairDone(tok) {
    localStorage.setItem(TOKEN_KEY, tok);
    $('sheet-pair').hidden = true;
    renderGlobalBanners();
    toast('Paired', 'ok');
  }

  $('pair-go').onclick = async (ev) => {
    const code = $('pair-code').value.replace(/\D/g, '');
    if (code.length !== 6) { toast('The code has 6 digits', 'warn'); return; }
    const btn = ev.currentTarget;
    btn.classList.add('busy');
    try {
      const r = await fetch('/api/pair', {
        method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.token) { toast(d.error || ('Pairing failed (' + r.status + ')'), 'err'); return; }
      await pairDone(d.token);
    } catch (e) {
      toast("Can't reach the sorter", 'err');
    } finally {
      btn.classList.remove('busy');
    }
  };
  $('pair-code').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('pair-go').click(); });

  $('pair-token-go').onclick = async (ev) => {
    const tok = $('pair-token').value.trim();
    if (!tok) { toast('Enter the token', 'warn'); return; }
    const btn = ev.currentTarget;
    btn.classList.add('busy');
    try {
      const r = await fetch('/api/auth/check', { method: 'POST', cache: 'no-store', headers: { 'X-Auth-Token': tok } });
      if (r.status === 401) { toast('Wrong token', 'err'); return; }
      if (!r.ok) { toast('Check failed (' + r.status + ')', 'err'); return; }
      $('pair-token').value = '';
      await pairDone(tok);
    } catch (e) {
      toast("Can't reach the sorter", 'err');
    } finally {
      btn.classList.remove('busy');
    }
  };

  $('pair-forget').onclick = async () => {
    if (!await confirmBox('Unpair this phone?', 'The token is removed from this phone. Pair again to use the controls.', 'Unpair', 'danger')) return;
    localStorage.removeItem(TOKEN_KEY);
    $('sheet-pair').hidden = true;
    renderGlobalBanners();
    toast('Unpaired');
  };

  // ── loops ────────────────────────────────────────────────────────────────
  function every(ms, fn) {
    const tick = async () => {
      if (document.visibilityState === 'visible') { try { await fn(); } catch (e) { /* next tick */ } }
      setTimeout(tick, ms);
    };
    setTimeout(tick, ms);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') { pollStatus(); pollThroughput(); pollB(); }
  });

  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* optional: shell cache only */ });
  }

  showTab(location.hash.slice(1) || 'run');
  renderGlobalBanners();
  pollStatus();
  pollThroughput();
  every(POLL_MS, pollStatus);
  every(5000, pollThroughput);
  every(POLL_MS, pollB);
  every(CAM_MS, () => (ui.tab === 'camera' && ui.camLive ? refreshCamera() : null));
})();
