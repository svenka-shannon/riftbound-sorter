"""
Hopper elevator: 28BYJ-48 5 V geared stepper + ULN2003 driver board turning a
T8 lead screw (8 mm lead) that raises the hopper floor (cad/hopper.scad), so
the top card always sits at the suction-cup pick height.

Wiring (BCM numbering; header pins in brackets):
  ULN2003 IN1 → GPIO 16 [36]     ULN2003 +  → 5 V (regulator #1 rail)
  ULN2003 IN2 → GPIO 19 [35]     ULN2003 −  → common GND
  ULN2003 IN3 → GPIO 20 [38]     motor plug → ULN2003 white JST (keyed)
  ULN2003 IN4 → GPIO 21 [40]
  Top-of-stack switch  (feeler-flag microswitch)  C → GND [34], NO → GPIO 12 [32]
  Bottom/home switch   (carriage lug microswitch) C → GND [30], NO → GPIO 13 [33]
Switches use the Pi's internal pull-ups: open = HIGH, pressed = LOW.

Boot / crash safety: GPIO 16–21 default to inputs with pull-DOWN, so all four
ULN2003 inputs read LOW = every coil off. With the coils off the 28BYJ-48's
64:1 gearbox (≈60–120 mN·m friction torque) holds the screw: the load
back-drives the T8×8 screw with only ≈4 mN·m, so the floor never drops.

Mechanics / timing (28BYJ-48 5 V, 50 Ω/coil, pull-in ≥34.3 mN·m @120 Hz,
≥300 g·cm @500 pps, idle in-traction > 600 Hz, out-traction > 1000 Hz):
  Half-step: 8 phases; gearbox 63.684:1 → 4075.77 half-steps per output rev.
  T8×8 lead screw → 8 mm/rev → 1 half-step ≈ 1.96 µm.
  RAISE  2.0 ms/step (500 Hz, inside the ≥300 g·cm @500 pps rating) ≈ 0.98 mm/s
         → one 0.33 mm card ≈ 0.34 s. Load 0.6 kg (217 cards + plate +
         carriage) needs ≈ 5.9 N × 8 mm / (2π × 0.5) ≈ 15 mN·m: ~2× margin.
  LOWER  ramps 3.0 → 1.6 ms/step (≤625 Hz, gravity-assisted) ≈ 1.2 mm/s,
         full 71.6 mm travel ≈ 60 s.
  Steps faster than 1.2 ms (833 Hz) are refused (pull-out limit ~1000 Hz).

Coils are released after every move (they draw ~200 mA and heat the motor
when held); the gearbox holds position.

If you later use an M8 threaded rod (1.25 mm/rev) instead: set LEAD_MM = 1.25.
Raising one card then takes ~1.7 s and a full lower ~8 min.
"""

import os
import time

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

if not _MOCK:
    import RPi.GPIO as GPIO

# ── Pins (BCM) ───────────────────────────────────────────────────────────────
STEPPER_PINS = (16, 19, 20, 21)   # ULN2003 IN1..IN4
TOP_SWITCH_PIN = 12               # feeler flag at pick height (NO contact to GND)
BOTTOM_SWITCH_PIN = 13            # home switch, carriage at the bottom (NO to GND)
SWITCH_ACTIVE_LEVEL = 0           # pressed = LOW (pull-up + NO contact to GND)

# ── Mechanics (keep in sync with cad/hopper.scad) ───────────────────────────
HALF_STEPS_PER_REV = 4075.7728    # 64 half-steps × 63.68395:1 gearbox
LEAD_MM = 8.0                     # T8×8 lead screw: 8 mm per revolution
STEPS_PER_MM = HALF_STEPS_PER_REV / LEAD_MM          # ≈ 509.5
UP_DIRECTION = 1                  # flip to -1 if "raise" moves the floor down

PICK_Z_MM = 86.9                  # pick_z: top of stack above the hopper base
PLATE_Z_MIN_MM = 15.0             # zp_min: plate top with the carriage 1 mm above the floor
PLATE_Z_HOME_MM = 15.3            # plate top where the carriage lug reaches the home switch OP
PLATE_Z_MAX_MM = 86.6             # soft top limit (zp_max): one card below pick_z
TRAVEL_MM = PLATE_Z_MAX_MM - PLATE_Z_MIN_MM          # 71.6
CARD_THICKNESS_MM = 0.33          # raw Riftbound card

# ── Timing ───────────────────────────────────────────────────────────────────
RAISE_STEP_S = 0.0020             # 500 Hz
LOWER_STEP_S = 0.0016             # 625 Hz cruise
RAMP_START_S = 0.0030             # first steps of every move (333 Hz)
RAMP_STEPS = 120                  # steps to go from RAMP_START_S to cruise
MIN_STEP_S = 0.0012               # never step faster (833 Hz)
DEBOUNCE_READS = 3                # consecutive pressed reads (1 per step) to accept
HOME_BACKOFF_MM = 0.5             # after hitting the home switch, back off up this much
HOME_MARGIN_MM = 10.0             # home() gives up after TRAVEL_MM + this
PLATE_Z_ZERO_MM = PLATE_Z_HOME_MM + HOME_BACKOFF_MM  # plate top at position 0 (after homing)
MAX_POS_MM = PLATE_Z_MAX_MM - PLATE_Z_ZERO_MM        # soft top limit, measured from position 0
TRIP_EXTRA_STEPS = 0              # extra half-steps after the top switch trips (calibration)

# Half-step sequence (IN1..IN4)
_SEQ = (
    (1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0), (0, 1, 1, 0),
    (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1),
)

_phase = 0          # index into _SEQ
_pos_steps = None   # half-steps above the home position (None = not homed)
_initialized = False

# Mock state: plate height and a simulated card stack
_mock_plate_mm = 40.0
_mock_cards = 150


def mock_set_cards(n: int) -> None:
    """MOCK only: set how many cards sit on the simulated plate."""
    global _mock_cards
    _mock_cards = max(0, int(n))


# ── Low level ────────────────────────────────────────────────────────────────
def _write_phase(idx: int) -> None:
    if _MOCK:
        return
    for pin, level in zip(STEPPER_PINS, _SEQ[idx]):
        GPIO.output(pin, level)


def _release() -> None:
    """De-energize all four coils (the gearbox holds the load)."""
    if _MOCK:
        return
    for pin in STEPPER_PINS:
        GPIO.output(pin, GPIO.LOW)


def _top_pressed() -> bool:
    if _MOCK:
        stack_top = _mock_plate_mm + _mock_cards * CARD_THICKNESS_MM
        return _mock_cards > 0 and stack_top >= PICK_Z_MM
    return GPIO.input(TOP_SWITCH_PIN) == SWITCH_ACTIVE_LEVEL


def _bottom_pressed() -> bool:
    if _MOCK:
        return _mock_plate_mm <= PLATE_Z_HOME_MM
    return GPIO.input(BOTTOM_SWITCH_PIN) == SWITCH_ACTIVE_LEVEL


def _wait_until(t: float) -> None:
    """Spin until perf_counter() reaches t. Step periods are ≤ 3 ms, and
    time.sleep() at that scale oversleeps by 0.1 ms (Linux) up to 5-10 ms
    (timer coalescing), which would cut the step rate several-fold. The spin
    only runs while the floor is moving (one core busy; ≤ ~1 s per card)."""
    while time.perf_counter() < t:
        pass


def _check_period(period_s: float) -> float:
    return max(period_s, MIN_STEP_S)


def _move(direction: int, max_steps: int, cruise_s: float, stop_when=None,
          deadline: float | None = None) -> tuple[int, str]:
    """
    Step up (+1) or down (-1) at most max_steps half-steps.
    stop_when: callable returning True when the move should end (checked once
    per step, debounced). Returns (steps_taken, reason) with reason one of
    "done", "switch", "timeout".
    """
    global _phase, _pos_steps, _mock_plate_mm
    cruise_s = _check_period(cruise_s)
    hits = 0
    taken = 0
    next_t = time.perf_counter()
    reason = "done"
    try:
        while taken < max_steps:
            if stop_when is not None:
                hits = hits + 1 if stop_when() else 0
                if hits >= DEBOUNCE_READS:
                    reason = "switch"
                    break
            if deadline is not None and time.perf_counter() > deadline:
                reason = "timeout"
                break
            _phase = (_phase + direction * UP_DIRECTION) % len(_SEQ)
            _write_phase(_phase)
            taken += 1
            if _pos_steps is not None:
                _pos_steps += direction
            if _MOCK:
                _mock_plate_mm += direction / STEPS_PER_MM
                continue   # no real-time pacing in mock mode
            # linear ramp from RAMP_START_S down to the cruise period
            if taken < RAMP_STEPS:
                period = RAMP_START_S + (cruise_s - RAMP_START_S) * taken / RAMP_STEPS
            else:
                period = cruise_s
            next_t += period
            _wait_until(next_t)
            if time.perf_counter() - next_t > period:
                next_t = time.perf_counter()   # fell behind (scheduler hiccup): don't burst
    finally:
        _release()
    return taken, reason


# ── Public API ───────────────────────────────────────────────────────────────
def init():
    global _initialized
    if _MOCK:
        print("[elevator] MOCK mode — simulated stack, no hardware")
        _initialized = True
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in STEPPER_PINS:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(TOP_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BOTTOM_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    _initialized = True
    print(f"[elevator] ULN2003 on GPIO {STEPPER_PINS}, top switch GPIO {TOP_SWITCH_PIN}, "
          f"bottom switch GPIO {BOTTOM_SWITCH_PIN}")


def home(timeout_s: float = 90.0) -> bool:
    """
    Lower the floor until the bottom (home) switch closes, then back off
    HOME_BACKOFF_MM and zero the position. Use before loading cards.
    Returns False if the switch was not reached (stuck, broken wire, timeout).
    """
    global _pos_steps
    deadline = time.perf_counter() + timeout_s
    if not _bottom_pressed():
        max_steps = int((TRAVEL_MM + HOME_MARGIN_MM) * STEPS_PER_MM)
        _, reason = _move(-1, max_steps, LOWER_STEP_S, _bottom_pressed, deadline)
        if reason != "switch":
            print(f"[elevator] home failed ({reason}) — bottom switch never closed")
            _pos_steps = None
            return False
    # back off so the switch releases; that point is position 0
    _pos_steps = None
    _move(+1, int(HOME_BACKOFF_MM * STEPS_PER_MM), RAISE_STEP_S)
    _pos_steps = 0
    return True


def raise_to_pick(timeout_s: float = 30.0) -> bool:
    """
    Step the floor up until the top-of-stack switch closes (top card at
    pick height). Returns True when the card is in position.
    Returns False on timeout or at the soft top limit — the hopper is empty
    (the plate passes under the feeler flag through its notch) or jammed.
    """
    if _top_pressed():
        return True
    if _pos_steps is None:
        print("[elevator] not homed — call home() first")
        return False
    deadline = time.perf_counter() + timeout_s
    remaining = int(MAX_POS_MM * STEPS_PER_MM) - _pos_steps
    if remaining <= 0:
        return False
    _, reason = _move(+1, remaining, RAISE_STEP_S, _top_pressed, deadline)
    if reason == "switch":
        if TRIP_EXTRA_STEPS:
            _move(+1, TRIP_EXTRA_STEPS, RAISE_STEP_S)
        return True
    print(f"[elevator] raise_to_pick: {'timeout' if reason == 'timeout' else 'top limit'} "
          f"at {position_mm():.1f} mm — hopper empty or stuck")
    return False


def lower(mm: float) -> float:
    """
    Lower the floor by `mm` (stops early at the home switch).
    Returns the distance actually moved in mm.
    """
    if mm <= 0:
        return 0.0
    steps = int(round(mm * STEPS_PER_MM))
    if _pos_steps is not None:
        steps = min(steps, _pos_steps + int(HOME_BACKOFF_MM * STEPS_PER_MM))
    taken, _ = _move(-1, steps, LOWER_STEP_S, _bottom_pressed)
    return taken / STEPS_PER_MM


def position_mm() -> float:
    """Plate travel above home in mm (nan if not homed)."""
    return float("nan") if _pos_steps is None else _pos_steps / STEPS_PER_MM


def cards_remaining_estimate() -> int:
    """Stack height / card thickness, valid while the top card is at pick height."""
    if _pos_steps is None:
        return -1
    plate_top = PLATE_Z_ZERO_MM + position_mm()
    return max(0, round((PICK_Z_MM - plate_top) / CARD_THICKNESS_MM))


def deinit():
    """De-energize the coils and free the pins (the gearbox holds the floor)."""
    global _initialized
    if _MOCK:
        _initialized = False
        return
    _release()
    GPIO.cleanup(list(STEPPER_PINS) + [TOP_SWITCH_PIN, BOTTOM_SWITCH_PIN])
    _initialized = False
