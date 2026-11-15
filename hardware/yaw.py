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
  * Hard limits: targets outside [LIMIT_MIN_DEG, LIMIT_MAX_DEG] = [-80, 175]
    are refused (the cable post is hit at about -90; the tube / lead loop must
    not over-twist). The approach detour is checked too.
  * Same-direction approach: move_to(..., approach=True) always ends moving UP
    (increasing yaw): a target below the current yaw is reached via
    target - APPROACH_UNDERSHOOT_DEG (3 deg).
  * Never re-zero during a run: home() is only called by prepare_machine() and
    the calibration API. During a run only check_released() (at every hopper
    visit) and verify_edge() (at parks / every N cards) LOOK at the switch;
    a mismatch raises LostSteps and the position is no longer trusted.
  * A move interrupted by an exception (Shutdown, pigpio error) stops the wave
    at once and marks the position untrusted (homed() False).

Homing (home()):
  pressed  → move UP (fast) until released (at most HOME_RELEASE_MAX_DEG), then
             HOME_BACKOFF_DEG more;
  released → move DOWN (fast) until pressed (at most HOME_SEARCH_MAX_DEG), back up
             slowly until released, then HOME_BACKOFF_DEG more;
  then approach the press edge from above one microstep at a time at
  HOME_SLOW_DEG_S: the first pressed step is yaw 0.

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
HOME_RELEASE_MAX_DEG = 95.0      # pressed zone is 0..-72 (+ ramp): release within ~88 deg
HOME_SEARCH_MAX_DEG = 190.0      # released: anywhere from +8 to +175
EDGE_CHECK_DEG = 1.0
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
    "HOME_SEARCH_MAX_DEG", "EDGE_CHECK_DEG", "UART_DEVICE", "UART_BAUD", "UART_ADDRESS",
    "RSENSE_OHM", "RUN_CURRENT_A", "HOLD_CURRENT_A"))

MAX_PULSES_PER_WAVE = 5000


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


def driver_registers() -> dict:
    """Register values configure_driver() writes."""
    cs_run, vsense = current_setting(RUN_CURRENT_A)
    hold_a = RUN_CURRENT_A if HOLD_CURRENT_A is None else HOLD_CURRENT_A
    r = RSENSE_OHM + 0.02
    vfs = 0.180 if vsense else 0.325
    cs_hold = max(0, min(31, round(hold_a * 32 * math.sqrt(2) * r / vfs) - 1))
    gconf = (1 << 6) | (1 << 7) | (1 << 8)        # pdn_disable, mstep_reg_select, multistep_filt
    chop = 0x10000053 & ~0x0F000000                # toff 3, hstrt 5, intpol (datasheet reset value)
    chop |= (_MRES[MICROSTEPS] << 24) | (2 << 15) | ((1 << 17) if vsense else 0)
    ihold_irun = (8 << 16) | (cs_run << 8) | cs_hold
    return {REG_GCONF: gconf, REG_CHOPCONF: chop, REG_IHOLD_IRUN: ihold_irun}


def driver_datagrams() -> list[bytes]:
    addrs = range(4) if UART_ADDRESS < 0 else (UART_ADDRESS,)
    regs = driver_registers()
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
        chunks = [pulses[i:i + MAX_PULSES_PER_WAVE] for i in range(0, len(pulses), MAX_PULSES_PER_WAVE)]
        try:
            for chunk in chunks:
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
        self.world.move_yaw(direction * len(intervals) * deg_per_step())

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


def configure_driver():
    """Write microsteps + currents over the write-only UART (cannot be verified)."""
    for dg in driver_datagrams():
        _backend.uart_write(dg)


def enable():
    global _enabled
    _backend.set_enable(True)
    _enabled = True
    time.sleep(0.02)


def disable():
    """Motor off: the arm can be pushed by hand, so the position is no longer trusted."""
    global _enabled, _homed
    if _backend is not None:
        _backend.set_enable(False)
    _enabled = False
    _homed = False


def homed() -> bool:
    return _homed


def position_deg() -> float | None:
    return _pos * deg_per_step() if _homed else None


def home_pressed() -> bool:
    """Switch pressed (arm at or below home), debounced: 3 equal reads."""
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
    direction = 1 if delta > 0 else -1
    _run(direction, trapezoid_intervals(abs(delta)), tick)
    _pos = target
    _last_dir = direction


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
    limit = deg_to_steps(max_deg)
    while moved < limit:
        if home_pressed() == want_pressed:
            return moved
        n = min(chunk_steps, limit - moved)
        _run(direction, constant_intervals(n, speed), tick)
        moved += n
        _pos += direction * n
    return moved if home_pressed() == want_pressed else None


def home(tick=None, release_max_deg: float | None = None, search_max_deg: float | None = None) -> None:
    """Find yaw 0 (see the module docstring). Raises HomingError / YawInterlockError."""
    global _pos, _homed, _last_dir
    _check_interlock()
    _homed = False
    configure_driver()
    enable()
    fast_chunk = max(1, deg_to_steps(0.5))
    slow_chunk = 1
    rmax = HOME_RELEASE_MAX_DEG if release_max_deg is None else release_max_deg
    smax = HOME_SEARCH_MAX_DEG if search_max_deg is None else search_max_deg
    if home_pressed():
        if _seek(+1, False, rmax, HOME_FAST_DEG_S, fast_chunk, tick) is None:
            raise HomingError(f"home switch still PRESSED after {rmax:g} deg of travel up — broken "
                              "wire (NC wiring reads a broken wire as pressed) or a stuck switch")
    else:
        if _seek(-1, True, smax, HOME_FAST_DEG_S, fast_chunk, tick) is None:
            raise HomingError(f"home switch never pressed in {smax:g} deg of travel down — switch "
                              "cradle not adjusted to the cam, or the switch is dead. CHECK the arm "
                              "is clear of the cable post before anything else")
        if _seek(+1, False, 3 * HOME_BACKOFF_DEG, HOME_SLOW_DEG_S * 4, fast_chunk, tick) is None:
            raise HomingError("home switch did not release when backing up off the edge")
    _run(+1, constant_intervals(deg_to_steps(HOME_BACKOFF_DEG), HOME_FAST_DEG_S), tick)
    if home_pressed():
        raise HomingError(f"home switch pressed {HOME_BACKOFF_DEG:g} deg above its release point")
    if _seek(-1, True, 2 * HOME_BACKOFF_DEG + 5.0, HOME_SLOW_DEG_S, slow_chunk, tick) is None:
        raise HomingError("home switch not found on the slow approach from above")
    _pos, _homed, _last_dir = 0, True, -1
    time.sleep(SETTLE_S)
    print("[yaw] homed: press edge = yaw 0")


def check_released(where: str = "the hopper") -> None:
    """Hopper visit: the switch MUST read released; pressed = lost steps."""
    global _homed
    if home_pressed():
        _homed = False
        raise LostSteps(f"home switch reads PRESSED at {where} (tracked yaw "
                        f"{_pos * deg_per_step():.2f} deg): steps were lost")


def verify_edge(tick=None) -> None:
    """Check the press edge without re-zeroing: released at +EDGE_CHECK_DEG,
    pressed at -EDGE_CHECK_DEG (approached from above)."""
    global _homed
    move_to(EDGE_CHECK_DEG, tick=tick)
    if home_pressed():
        _homed = False
        raise LostSteps(f"home switch pressed at +{EDGE_CHECK_DEG:g} deg: the arm is lower than tracked")
    move_to(-EDGE_CHECK_DEG, tick=tick)
    if not home_pressed():
        _homed = False
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
