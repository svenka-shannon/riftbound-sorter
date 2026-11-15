"""
Option B yaw axis: NEMA 17 pancake, direct drive, on a TMC2209 (cad_b/README.md
round 5, "Electronics notes").

Pins (BCM; cad_b/README.md "Pin map (option B)"):
  STEP_PIN 23, DIR_PIN 24   step pulses from pigpio DMA waveforms (pigpiod)
  EN_PIN 25                 TMC2209 ENN, active LOW. config.txt "gpio=25=ip,pu"
                            (scripts/setup.sh) keeps the motor OFF during boot
  HOME_PIN 22               KW12-3 wired NC: COM → GND, NC → GPIO (pull-up).
                            Released = contact closed = LOW; pressed (or a broken
                            wire) = HIGH. The cam rim holds it pressed for every arm
                            angle from 0 down to about -72; released from ~+8 up.
  UART TX (GPIO 14)         write-only to PDN_UART: microsteps, IRUN, IHOLD = IRUN

Units: the position is kept in microsteps from HOME (yaw 0 = the press edge,
approached from above); 1/16 microsteps = 0.1125 deg/step.

Safety rules enforced HERE (sorter_b.py relies on them):
  * Interlock: every move (and homing) calls the registered interlock first
    (sorter_b registers lift.yaw_permitted: full lift + cup hanging free).
    No interlock registered → refused.
  * Hard limits: targets outside [LIMIT_MIN_DEG, LIMIT_MAX_DEG] = [-64, 175]
    are refused. -64 keeps the arm INSIDE the home cam (switch pressed from 0
    down to -72) with margin, so the switch can never read "released" below
    home and send a homing search down into the cable post (~ -90); 175 keeps
    the tube / lead loop from over-twisting. The approach detour is checked too.
  * Same-direction approach: move_to(..., approach=True) always ends moving UP
    (increasing yaw): a target below the current yaw is reached via
    target - APPROACH_UNDERSHOOT_DEG (3 deg).
  * Never re-zero during a run: home() is only called by prepare_machine() and
    the calibration API. During a run only check_released() (at every hopper
    visit) and verify_edge() (at parks / every N cards) LOOK at the switch;
    a mismatch raises LostSteps and the position is no longer trusted.
  * A move interrupted by an exception (Shutdown, pigpio error) stops the wave
    at once and marks the position untrusted (homed() False).

Position hint (HINT_FILE, data/yaw_hint.json): before every move the interval
the arm will pass through is written, after it the end position — atomically
and fsynced, like hardware/instance.py — with "trusted". A kill or power cut
mid-move therefore still leaves a bound on where the arm is. Lost steps and
motor_off (arm may be pushed by hand) make it untrusted; the operator can
re-declare it (sorter_b.declare_position after positioning the arm by hand).

Homing (home()) at HOME_CURRENT_A (a stall against the cable post at that
current hurts nothing), every search bounded by the hint:
  pressed  → up until released, at most from the hint's low end (never below
             -72) to RELEASED_FROM + margin. A hint far ABOVE the cam with the
             switch pressed = broken NC wire → refused without moving.
  released → down until pressed, at most from the hint's high end to 0 +
             margin, back up slowly until released. A hint INSIDE the cam with
             the switch released = stuck switch / moved arm → refused. A hint
             BELOW the cam (< -72): up until pressed first.
  no trusted hint → only NOHINT_SEARCH_DEG (20 deg: from park to past the
             edge) in either direction, else refused: position the arm by hand
             at park and declare it in the UI.
then HOME_BACKOFF_DEG up and the press edge approached from above one microstep
at a time at HOME_SLOW_DEG_S: the first pressed step is yaw 0. The run current
is restored afterwards.

Motion profile: trapezoid (ACCEL_DEG_S2 300, MAX_SPEED_DEG_S 120), then SETTLE_S
(150 ms: the arm rings at ~5-7 Hz). The whole move is ONE pigpio waveform (a
255 deg sweep is ~2300 steps = ~4600 pulses, inside pigpio's default buffer);
longer pulse trains are split into several waves sent back to back.

UART (write-only, configure_driver()): GCONF (pdn_disable, mstep_reg_select,
internal current reference), CHOPCONF (MRES for MICROSTEPS, vsense, toff 3,
interpolation), IHOLD_IRUN (IRUN = IHOLD from RUN_CURRENT_A / RSENSE_OHM).
Nothing can be read back, so the datagrams go to EVERY slave address (0-3) by
default (UART_ADDRESS -1): whatever MS1/MS2 say, the driver gets them. Wire
MS1 = MS2 = VIO anyway: then the pin default is 1/16 too, so a dead UART line
can never silently halve the step size (cad_b/README.md, pin map notes).
"""

from __future__ import annotations

import math
import os
import sys
import time

from hardware import b_geometry as geo
from hardware import machine_config

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

STEP_PIN = 23
DIR_PIN = 24
EN_PIN = 25
HOME_PIN = 22
HOME_SWITCH_NC = True
DIR_INVERT = False
FULL_STEPS_PER_REV = 200
MICROSTEPS = 16
MAX_SPEED_DEG_S = 120.0
ACCEL_DEG_S2 = 300.0
SETTLE_S = 0.15
STEP_PULSE_US = 5
APPROACH_UNDERSHOOT_DEG = 3.0
LIMIT_MIN_DEG = geo.LIMIT_MIN_DEG
LIMIT_MAX_DEG = geo.LIMIT_MAX_DEG
HOME_FAST_DEG_S = 20.0
HOME_SLOW_DEG_S = 2.0
HOME_BACKOFF_DEG = 5.0
HOME_RELEASE_MAX_DEG = 95.0      # hard cap on any upward homing search
HOME_SEARCH_MAX_DEG = 190.0      # hard cap on any downward homing search
NOHINT_SEARCH_DEG = 20.0         # no trusted position hint: search only this far
HINT_MARGIN_DEG = 5.0            # coast / rounding margin around the hint
HOME_CURRENT_A = 0.3             # run current while homing (stall at the post is harmless)
EDGE_CHECK_DEG = 1.0
EDGE_APPROACH_DEG = 3.0          # the +EDGE check point is approached from this far above
UART_DEVICE = "/dev/serial0"
UART_BAUD = 115200
UART_ADDRESS = -1                # -1 = write to all four slave addresses
RSENSE_OHM = 0.11                # typical StepStick TMC2209 module
RUN_CURRENT_A = 0.7
HOLD_CURRENT_A = None            # None = IHOLD = IRUN (full stiffness at the stations)

machine_config.apply(sys.modules[__name__], "yaw", (
    "STEP_PIN", "DIR_PIN", "EN_PIN", "HOME_PIN", "HOME_SWITCH_NC", "DIR_INVERT",
    "FULL_STEPS_PER_REV", "MICROSTEPS", "MAX_SPEED_DEG_S", "ACCEL_DEG_S2", "SETTLE_S",
    "STEP_PULSE_US", "APPROACH_UNDERSHOOT_DEG", "LIMIT_MIN_DEG", "LIMIT_MAX_DEG",
    "HOME_FAST_DEG_S", "HOME_SLOW_DEG_S", "HOME_BACKOFF_DEG", "HOME_RELEASE_MAX_DEG",
    "HOME_SEARCH_MAX_DEG", "NOHINT_SEARCH_DEG", "HINT_MARGIN_DEG", "EDGE_CHECK_DEG",
    "EDGE_APPROACH_DEG", "HOME_CURRENT_A", "UART_DEVICE", "UART_BAUD", "UART_ADDRESS",
    "RSENSE_OHM", "RUN_CURRENT_A", "HOLD_CURRENT_A"))

MAX_PULSES_PER_WAVE = 5000       # one pigpio wave; longer pulse trains are refused

from pathlib import Path as _Path
HINT_FILE = _Path(__file__).resolve().parent.parent / "data" / (
    "yaw_hint.mock.json" if _MOCK else "yaw_hint.json")


class YawError(RuntimeError):
    """The yaw axis could not do what was asked (base class)."""


class YawLimitError(YawError):
    """Target outside the hard software limits (refused, nothing moved)."""


class YawInterlockError(YawError):
    """The interlock (lift at full height, cup hanging free) refused the move."""


class YawNotHomed(YawError):
    """Position unknown / untrusted: home first."""


class HomingError(YawError):
    """The home switch did not behave as the cam geometry says it must."""


class LostSteps(YawError):
    """The home switch disagrees with the tracked position: steps were lost."""


def deg_per_step() -> float:
    return 360.0 / (FULL_STEPS_PER_REV * MICROSTEPS)


def deg_to_steps(deg: float) -> int:
    return int(round(deg / deg_per_step()))


# ── motion profile ───────────────────────────────────────────────────────────
def trapezoid_intervals(n: int, vmax_deg_s: float = None, accel_deg_s2: float = None) -> list[float]:
    """Seconds between consecutive step pulses for an n-step trapezoid move
    (triangle if it never reaches vmax). Symmetric accel / decel."""
    if n <= 0:
        return []
    v = (vmax_deg_s or MAX_SPEED_DEG_S) / deg_per_step()          # steps/s
    a = (accel_deg_s2 or ACCEL_DEG_S2) / deg_per_step()           # steps/s²
    n_acc = min(int(v * v / (2 * a)), n // 2)
    t_acc_end = math.sqrt(2 * n_acc / a) if n_acc else 0.0
    v_reach = a * t_acc_end if n_acc else v

    def t_at(i):                       # time when step i (1..n) is issued
        if i <= n_acc:
            return math.sqrt(2 * i / a)
        if i <= n - n_acc:
            return t_acc_end + (i - n_acc) / max(v_reach, 1e-9)
        t_dec0 = t_acc_end + (n - 2 * n_acc) / max(v_reach, 1e-9)
        k = n - i                      # steps left
        return t_dec0 + (math.sqrt(2 * n_acc / a) - math.sqrt(2 * k / a))
    times = [0.0] + [t_at(i) for i in range(1, n + 1)]
    first = math.sqrt(2 / a)
    out = [first] + [max(times[i + 1] - times[i], 1e-5) for i in range(1, n)]
    return out


def constant_intervals(n: int, speed_deg_s: float) -> list[float]:
    return [deg_per_step() / speed_deg_s] * n


# ── TMC2209 UART (write-only) ────────────────────────────────────────────────
REG_GCONF, REG_IHOLD_IRUN, REG_CHOPCONF = 0x00, 0x10, 0x6C
_MRES = {256: 0, 128: 1, 64: 2, 32: 3, 16: 4, 8: 5, 4: 6, 2: 7, 1: 8}


def tmc_crc8(data: bytes) -> int:
    """CRC8 as in the TMC2209 datasheet (polynomial x^8 + x^2 + x + 1, LSB first)."""
    crc = 0
    for byte in data:
        for _ in range(8):
            if ((crc >> 7) ^ (byte & 0x01)) & 1:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
            byte >>= 1
    return crc


def tmc_write_datagram(addr: int, reg: int, value: int) -> bytes:
    d = bytes([0x05, addr & 0x03, (reg & 0x7F) | 0x80]) + int(value & 0xFFFFFFFF).to_bytes(4, "big")
    return d + bytes([tmc_crc8(d)])


def current_setting(i_rms: float, rsense: float = None) -> tuple[int, bool]:
    """(CS 0..31, vsense) for an RMS current: I = (CS+1)/32 · Vfs/(Rsense+0.02 Ω)/√2,
    Vfs 0.180 V (vsense 1) or 0.325 V. vsense 1 when CS fits (finer steps)."""
    r = (rsense or RSENSE_OHM) + 0.02
    for vsense, vfs in ((True, 0.180), (False, 0.325)):
        cs = round(i_rms * 32 * math.sqrt(2) * r / vfs) - 1
        if 0 <= cs <= 31:
            return cs, vsense
    return (31, False) if i_rms > 0 else (0, True)


def driver_registers(run_a: float | None = None) -> dict:
    """Register values configure_driver() writes (run_a: override, e.g. homing)."""
    run_a = RUN_CURRENT_A if run_a is None else run_a
    cs_run, vsense = current_setting(run_a)
    hold_a = run_a if (HOLD_CURRENT_A is None or run_a != RUN_CURRENT_A) else HOLD_CURRENT_A
    r = RSENSE_OHM + 0.02
    vfs = 0.180 if vsense else 0.325
    cs_hold = max(0, min(31, round(hold_a * 32 * math.sqrt(2) * r / vfs) - 1))
    gconf = (1 << 6) | (1 << 7) | (1 << 8)        # pdn_disable, mstep_reg_select, multistep_filt
    chop = 0x10000053 & ~0x0F000000                # toff 3, hstrt 5, intpol (datasheet reset value)
    chop |= (_MRES[MICROSTEPS] << 24) | (2 << 15) | ((1 << 17) if vsense else 0)
    ihold_irun = (8 << 16) | (cs_run << 8) | cs_hold
    return {REG_GCONF: gconf, REG_CHOPCONF: chop, REG_IHOLD_IRUN: ihold_irun}


def driver_datagrams(run_a: float | None = None) -> list[bytes]:
    addrs = range(4) if UART_ADDRESS < 0 else (UART_ADDRESS,)
    regs = driver_registers(run_a)
    return [tmc_write_datagram(a, reg, regs[reg]) for a in addrs
            for reg in (REG_GCONF, REG_CHOPCONF, REG_IHOLD_IRUN)]


# ── backends ─────────────────────────────────────────────────────────────────
class _PigpioBackend:
    def __init__(self):
        import pigpio
        self.pg = pigpio
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise YawError("cannot reach pigpiod — sudo systemctl enable --now pigpiod "
                           "(scripts/setup.sh installs it)")
        self.pi.write(EN_PIN, 1)                 # driver OFF before anything else
        self.pi.write(STEP_PIN, 0)
        self.pi.write(DIR_PIN, 0)
        self.pi.set_mode(HOME_PIN, pigpio.INPUT)
        self.pi.set_pull_up_down(HOME_PIN, pigpio.PUD_UP)
        self.pi.wave_clear()

    def home_raw(self) -> bool:
        return self.pi.read(HOME_PIN) == 1      # NC open (pressed) or broken wire → HIGH

    def set_enable(self, on: bool):
        self.pi.write(EN_PIN, 0 if on else 1)

    def run(self, direction: int, intervals: list[float], tick=None):
        pg, pi = self.pg, self.pi
        pi.write(DIR_PIN, (1 if direction > 0 else 0) ^ (1 if DIR_INVERT else 0))
        time.sleep(0.001)                        # DIR setup before the first STEP
        mask = 1 << STEP_PIN
        pulses = []
        for dt in intervals:
            low = max(int(round(dt * 1e6)) - STEP_PULSE_US, STEP_PULSE_US)
            pulses += [pg.pulse(mask, 0, STEP_PULSE_US), pg.pulse(0, mask, low)]
        try:
            for chunk in (pulses,):
                pi.wave_add_new()
                pi.wave_add_generic(chunk)
                wid = pi.wave_create()
                if wid < 0:
                    raise YawError(f"pigpio wave_create failed ({wid})")
                try:
                    pi.wave_send_once(wid)
                    while pi.wave_tx_busy():
                        if tick:
                            tick()
                        time.sleep(0.005)
                finally:
                    pi.wave_delete(wid)
        except BaseException:
            try:
                pi.wave_tx_stop()
            except Exception:
                pass
            raise

    def uart_write(self, data: bytes):
        h = self.pi.serial_open(UART_DEVICE, UART_BAUD)
        try:
            self.pi.serial_write(h, data)
            time.sleep(len(data) * 10.0 / UART_BAUD + 0.005)
        finally:
            self.pi.serial_close(h)

    def close(self):
        try:
            self.pi.wave_tx_stop()
            self.pi.write(EN_PIN, 1)
        finally:
            self.pi.stop()


class _MockBackend:
    """Simulated driver; the world knows whether the run current is the homing one."""

    def __init__(self):
        self.uart = []
        self.runs = []                           # (direction, n, intervals) — tests inspect profiles

    @property
    def world(self):
        from hardware import b_mock
        return b_mock.WORLD

    def home_raw(self) -> bool:
        return self.world.home_pressed()

    def set_enable(self, on: bool):
        self.world.yaw_enabled = on

    def run(self, direction: int, intervals: list[float], tick=None):
        self.runs.append((direction, len(intervals), intervals))
        if tick:
            tick()
        self.world.move_yaw(direction * len(intervals) * deg_per_step(),
                            low_current=_current_a <= HOME_CURRENT_A + 1e-9)

    def uart_write(self, data: bytes):
        self.uart.append(bytes(data))

    def close(self):
        self.world.yaw_enabled = False


# ── state ────────────────────────────────────────────────────────────────────
_backend = None
_pos = 0                 # microsteps from home (meaningful only when _homed)
_homed = False
_last_dir = 0            # +1: the last motion ended moving up; -1: down
_enabled = False
_interlock = None
_current_a = RUN_CURRENT_A


# ── position hint (data/yaw_hint.json) ──────────────────────────────────────
def save_hint(lo: float, hi: float, trusted: bool = True) -> None:
    """Atomically + durably record that the arm is within [lo, hi] deg."""
    import json
    import tempfile
    from hardware import instance
    path = HINT_FILE
    data = {"lo": round(min(lo, hi), 4), "hi": round(max(lo, hi), 4), "trusted": bool(trusted),
            "ts": time.time()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps(data))
                fh.flush()
                os.fsync(fh.fileno())
            instance._match_parent_owner(tmp)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        instance.fsync_dir(path.parent)
    except OSError as exc:
        print(f"[yaw] WARNING: could not save the position hint {path}: {exc}")


def load_hint():
    """(lo, hi) deg if a TRUSTED hint is on file, else None."""
    import json
    try:
        d = json.loads(HINT_FILE.read_text())
        lo, hi = float(d["lo"]), float(d["hi"])
        if d.get("trusted") is True and math.isfinite(lo) and math.isfinite(hi):
            return min(lo, hi), max(lo, hi)
    except Exception:
        pass
    return None


def distrust_hint() -> None:
    h = None
    try:
        import json
        d = json.loads(HINT_FILE.read_text())
        h = (float(d["lo"]), float(d["hi"]))
    except Exception:
        pass
    save_hint(*(h or (0.0, 0.0)), trusted=False)


def set_interlock(fn) -> None:
    """fn() -> (ok: bool, why: str); called before every move and homing."""
    global _interlock
    _interlock = fn


def init():
    """Open the driver pins (motor stays DISABLED) and write the UART config."""
    global _backend, _homed, _enabled, _pos, _last_dir
    if _backend is None:
        _backend = _MockBackend() if _MOCK else _PigpioBackend()
    _homed, _enabled, _pos, _last_dir = False, False, 0, 0
    _backend.set_enable(False)
    configure_driver()
    print(f"[yaw] TMC2209 STEP {STEP_PIN} DIR {DIR_PIN} EN {EN_PIN}, home switch GPIO {HOME_PIN} "
          f"(NC), 1/{MICROSTEPS} = {deg_per_step():.4f} deg/step")


def backend():
    return _backend


def configure_driver(run_a: float | None = None):
    """Write microsteps + currents over the write-only UART (cannot be verified).
    run_a: run (and hold) current override, e.g. HOME_CURRENT_A while homing."""
    global _current_a
    for dg in driver_datagrams(run_a):
        _backend.uart_write(dg)
    _current_a = RUN_CURRENT_A if run_a is None else run_a


def enable():
    global _enabled
    _backend.set_enable(True)
    _enabled = True
    time.sleep(0.02)


def disable(distrust: bool = False):
    """Motor off: the position is no longer trusted for moves (home again).
    distrust=True also marks the saved hint untrusted (the operator is about
    to turn the arm by hand)."""
    global _enabled, _homed
    if _backend is not None:
        _backend.set_enable(False)
    _enabled = False
    _homed = False
    if distrust:
        distrust_hint()


def homed() -> bool:
    return _homed


def position_deg() -> float | None:
    return _pos * deg_per_step() if _homed else None


def home_pressed() -> bool:
    """Switch pressed (arm at or below home), debounced: two consecutive equal
    reads 1 ms apart (up to 5 tries; still flickering → "pressed")."""
    for _ in range(5):
        a = _backend.home_raw()
        if not _MOCK:
            time.sleep(0.001)
        if _backend.home_raw() == a:
            return a
    return True


def _check_interlock():
    if _interlock is None:
        raise YawInterlockError("no lift interlock registered — yaw refuses to move")
    ok, why = _interlock()
    if not ok:
        raise YawInterlockError(why)


def _check_limits(deg: float, what: str = "target"):
    if not LIMIT_MIN_DEG - 1e-9 <= deg <= LIMIT_MAX_DEG + 1e-9:
        raise YawLimitError(f"yaw {what} {deg:.2f} deg is outside the hard limits "
                            f"[{LIMIT_MIN_DEG:g}, {LIMIT_MAX_DEG:g}] (cable post / lead loop)")


def _run(direction: int, intervals: list[float], tick=None):
    """Step; any exception stops the wave and makes the position untrusted."""
    global _homed
    if not _enabled:
        enable()
    try:
        _backend.run(direction, intervals, tick)
    except BaseException:
        _homed = False
        raise


def _move_steps(target: int, tick=None):
    global _pos, _last_dir
    delta = target - _pos
    if delta == 0:
        return
    if 2 * abs(delta) > MAX_PULSES_PER_WAVE:
        raise YawError(f"move of {abs(delta)} steps exceeds one pigpio wave "
                       f"({MAX_PULSES_PER_WAVE // 2} steps) — refused")
    direction = 1 if delta > 0 else -1
    a, b = _pos * deg_per_step(), target * deg_per_step()
    save_hint(a, b, True)                 # the arm is somewhere in here until it arrives
    _run(direction, trapezoid_intervals(abs(delta)), tick)
    _pos = target
    _last_dir = direction
    save_hint(b, b, True)


def move_to(target_deg: float, approach: bool = False, tick=None, settle: bool = True) -> float:
    """Move to target_deg (limits + interlock checked). approach=True: end the
    move travelling UP (via target - APPROACH_UNDERSHOOT_DEG if needed)."""
    if not _homed:
        raise YawNotHomed("yaw position unknown — home first")
    _check_limits(target_deg)
    target = deg_to_steps(target_deg)
    legs = [target]
    if approach and (target < _pos or (target == _pos and _last_dir < 0)):
        via_deg = target_deg - APPROACH_UNDERSHOOT_DEG
        _check_limits(via_deg, "approach detour")
        legs = [deg_to_steps(via_deg), target]
    for leg in legs:
        if leg == _pos:
            continue
        _check_interlock()
        _move_steps(leg, tick)
        if settle:
            time.sleep(SETTLE_S)
    return position_deg()


def move_by(delta_deg: float, tick=None) -> float:
    if not _homed:
        raise YawNotHomed("yaw position unknown — home first")
    return move_to(position_deg() + delta_deg, approach=False, tick=tick)


def _seek(direction: int, want_pressed: bool, max_deg: float, speed: float,
          chunk_steps: int, tick=None) -> int | None:
    """Constant-speed chunks until the switch reads want_pressed; steps moved, or None."""
    global _pos
    moved = 0
    limit = deg_to_steps(max(0.0, max_deg))
    while moved < limit:
        if home_pressed() == want_pressed:
            return moved
        n = min(chunk_steps, limit - moved)
        _run(direction, constant_intervals(n, speed), tick)
        moved += n
        _pos += direction * n
    return moved if home_pressed() == want_pressed else None


def _plan_home(pressed: bool, hint) -> dict:
    """Which way and how far the homing searches may go (pure; see the docstring).
    Returns {"first": ("up_until_pressed", deg) | None, "up_release": deg | None,
    "down_press": deg | None} or raises HomingError (refused, nothing moves)."""
    m = HINT_MARGIN_DEG
    low, rel = geo.HOME_CAM_LOW_DEG, geo.RELEASED_FROM_DEG
    if hint is None:
        if pressed:
            return {"first": None, "up_release": NOHINT_SEARCH_DEG, "down_press": None}
        return {"first": None, "up_release": None, "down_press": NOHINT_SEARCH_DEG}
    lo, hi = hint[0] - m, hint[1] + m
    if pressed:
        if lo > rel:
            raise HomingError(f"home switch reads PRESSED but the arm was last at {hint[0]:.1f}.."
                              f"{hint[1]:.1f} deg, above the cam — broken switch wire (NC reads a "
                              "broken wire as pressed)? Nothing moved")
        up = min(rel + m - max(lo, low), HOME_RELEASE_MAX_DEG)
        return {"first": None, "up_release": up, "down_press": None}
    if hi < low + m:                      # arm below the cam: released there too
        up_press = min(low - lo + m, HOME_RELEASE_MAX_DEG)
        return {"first": ("up_until_pressed", up_press),
                "up_release": min(rel + m - low, HOME_RELEASE_MAX_DEG), "down_press": None}
    if hint[1] < -m and hint[0] > low + m:
        raise HomingError(f"home switch reads RELEASED but the arm was last at {hint[0]:.1f}.."
                          f"{hint[1]:.1f} deg, inside the cam where it must be pressed — switch "
                          "stuck / cradle misadjusted, or the arm was moved by hand. Nothing moved")
    down = min(max(hi, 0.0) + m, HOME_SEARCH_MAX_DEG)
    return {"first": None, "up_release": None, "down_press": down}


def home(tick=None) -> None:
    """Find yaw 0 (see the module docstring). Raises HomingError / YawInterlockError."""
    global _pos, _homed, _last_dir
    _check_interlock()
    _homed = False
    hint = load_hint()
    pressed = home_pressed()
    plan = _plan_home(pressed, hint)             # may refuse before anything moves
    fast_chunk = max(1, deg_to_steps(0.5))
    slow_chunk = 1
    base_lo, base_hi = hint if hint else (geo.HOME_CAM_LOW_DEG, geo.LIMIT_MAX_DEG)
    configure_driver(HOME_CURRENT_A)
    enable()
    try:
        if plan["first"]:
            _, d = plan["first"]
            save_hint(base_lo - HINT_MARGIN_DEG, base_hi + d, hint is not None)
            if _seek(+1, True, d, HOME_FAST_DEG_S, fast_chunk, tick) is None:
                raise HomingError(f"home switch not pressed within {d:.0f} deg up from below the cam")
        if plan["up_release"] is not None:
            d = plan["up_release"]
            save_hint(base_lo - HINT_MARGIN_DEG, base_hi + d + HINT_MARGIN_DEG, hint is not None)
            if _seek(+1, False, d, HOME_FAST_DEG_S, fast_chunk, tick) is None:
                distrust_hint()
                raise HomingError(
                    f"home switch still PRESSED after {d:.0f} deg up — broken wire, stuck switch, "
                    + ("or no trusted position hint: turn the motor off, put the arm at the park "
                       "pose by hand and declare it in the UI" if hint is None else
                       "or the arm is not where it was last recorded"))
        else:
            d = plan["down_press"]
            save_hint(base_lo - d - HINT_MARGIN_DEG, base_hi + HINT_MARGIN_DEG, hint is not None)
            if _seek(-1, True, d, HOME_FAST_DEG_S, fast_chunk, tick) is None:
                distrust_hint()
                raise HomingError(
                    f"home switch never pressed in {d:.0f} deg of travel down — "
                    + ("no trusted position hint: turn the motor off, put the arm at the park pose "
                       "by hand and declare it in the UI" if hint is None else
                       "switch cradle not adjusted to the cam, a dead switch, or the arm was moved"))
            if _seek(+1, False, 3 * HOME_BACKOFF_DEG, HOME_SLOW_DEG_S * 4, fast_chunk, tick) is None:
                raise HomingError("home switch did not release when backing up off the edge")
        _run(+1, constant_intervals(deg_to_steps(HOME_BACKOFF_DEG), HOME_FAST_DEG_S), tick)
        if home_pressed():
            raise HomingError(f"home switch pressed {HOME_BACKOFF_DEG:g} deg above its release point")
        if _seek(-1, True, 2 * HOME_BACKOFF_DEG + 5.0, HOME_SLOW_DEG_S, slow_chunk, tick) is None:
            raise HomingError("home switch not found on the slow approach from above")
    finally:
        configure_driver()                       # back to the run current
    _pos, _homed, _last_dir = 0, True, -1
    save_hint(0.0, 0.0, True)
    time.sleep(SETTLE_S)
    print("[yaw] homed: press edge = yaw 0")


def check_released(where: str = "the hopper") -> None:
    """Hopper visit: the switch MUST read released; pressed = lost steps."""
    global _homed
    if home_pressed():
        _homed = False
        distrust_hint()
        raise LostSteps(f"home switch reads PRESSED at {where} (tracked yaw "
                        f"{_pos * deg_per_step():.2f} deg): steps were lost")


def verify_edge(tick=None) -> None:
    """Check the press edge without re-zeroing: released at +EDGE_CHECK_DEG
    approached from ABOVE (from +EDGE + EDGE_APPROACH_DEG, so the switch's
    differential travel on the cam ramp never matters), then pressed at
    -EDGE_CHECK_DEG."""
    global _homed
    if position_deg() is not None and position_deg() < EDGE_CHECK_DEG + EDGE_APPROACH_DEG:
        move_to(EDGE_CHECK_DEG + EDGE_APPROACH_DEG, tick=tick)
    move_to(EDGE_CHECK_DEG, tick=tick)
    if home_pressed():
        _homed = False
        distrust_hint()
        raise LostSteps(f"home switch pressed at +{EDGE_CHECK_DEG:g} deg: the arm is lower than tracked")
    move_to(-EDGE_CHECK_DEG, tick=tick)
    if not home_pressed():
        _homed = False
        distrust_hint()
        raise LostSteps(f"home switch released at -{EDGE_CHECK_DEG:g} deg: the arm is higher than tracked")


def deinit():
    """Motor disabled, pigpio released. Idempotent."""
    global _backend, _homed, _enabled
    if _backend is not None:
        try:
            _backend.close()
        except Exception as exc:
            print(f"[yaw] close failed: {exc!r}")
    _backend = None
    _homed = _enabled = False
