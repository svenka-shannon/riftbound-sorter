"""
Simulated option B machine for MOCK_HARDWARE=1 (dev runs and tests).

One World holds the physical truth: the arm's REAL yaw (which may differ from
the commanded one after injected lost steps), the lift's link angle, the pump,
what the cup holds, and the cards in the hopper, on the bed and in each bin.
The B drivers read their sensors from it in MOCK mode:
  yaw.py    home switch (cam: pressed for -72 <= yaw <= 0; once pressed it releases
            only HOME_HYST_DEG higher — differential travel on the cam ramp),
            moves (plus any injected slip), the cable post at -90 (at the homing
            current a stall there is harmless and logged as "stall", else "crash")
  lift.py   link angle on every servo write
  touch.py  contact OPEN while the cup (or the card under it) rests on a surface
  loadcell  the bed load (cards on the bed + the slider resting on it)
  vacuum    pump on → the top card under a touching cup is picked;
            pump off → the held card drops onto whatever is under it
Cards are weights (1.75 g single, 3.5 g a stuck double). Every hazard a test
must prove never happens is logged in World.events:
  ("drop", station, height_mm)   card released with the cup more than DROP_OK_MM above the surface
  ("crash", what)                slider over-travel, cable post, lowering onto a wall
  ("yaw_low", th)                yaw moved with the lift below full height
The hopper floor has the Ø32 hole under the cup (cad 029e479): with no card
left the cup drops through and never touches.
"""

from hardware import b_geometry as geo

SINGLE_G = 1.75
DOUBLE_G = 3.5
SLIDER_G = 30.0          # slider + cup + tee resting on the bed when the cup touches it
DROP_OK_MM = 1.0
HOME_HYST_DEG = 1.5


class World:
    def __init__(self, hopper_cards: int = 20, yaw: float = -10.0):
        self.yaw = yaw                # real arm angle (deg); unknown to the software at start
        self.th = geo.TH_FULL         # real link angle
        self.pump = False
        self.cup = []                 # weights held on the cup (0 or 1 item)
        self.hopper = [SINGLE_G] * hopper_cards     # bottom → top
        self.bed = []
        self.bins = {n: [] for n in geo.STATIONS[2:]}
        self.seal_fail = 0            # next N pump-ons pick nothing
        self.release_fail = 0         # next N pump-offs keep the card on the cup
        self.slip_next_deg = 0.0      # added to the next yaw move (lost steps)
        self.home_wire_broken = False # NC wire broken: reads pressed
        self.touch_stuck_closed = False
        self.yaw_enabled = False
        self.events = []
        self._home_state = None

    # ── geometry ────────────────────────────────────────────────────────────
    def station(self):
        """Station whose pocket is under the cup (design angles), or None."""
        for name in geo.STATIONS:
            if abs(geo.NOMINAL_YAW[name] - self.yaw) <= geo.STATION_HALF_WIDTH_DEG:
                return name
        return None

    def _pile(self, name):
        if name == "hopper":
            return self.hopper
        if name == "scan":
            return self.bed
        return self.bins.get(name)

    @staticmethod
    def _cards(items):
        return sum(2 if w > SINGLE_G * 1.5 else 1 for w in items)

    def surface_z(self):
        """Height of whatever the cup would land on (mm), or None (nothing: open hole)."""
        name = self.station()
        if name is None:
            return 0.0 if self.yaw <= geo.ST0_DEG - geo.STATION_HALF_WIDTH_DEG else geo.WALL_TOP_Z_MM
        pile = self._pile(name)
        base = geo.BED_TOP_Z_MM if name == "scan" else geo.FLOOR_Z_MM
        if name == "hopper" and not pile:
            return None                # Ø32 hole under the cup: nothing to touch
        return base + geo.CARD_T_MM * self._cards(pile)

    def cup_bottom_z(self):
        return geo.lip_z(self.th) - (geo.CARD_T_MM * self._cards(self.cup))

    def touching(self):
        s = self.surface_z()
        return s is not None and self.cup_bottom_z() <= s + 1e-6

    # ── sensors ─────────────────────────────────────────────────────────────
    def touch_open(self):
        if self.touch_stuck_closed:
            return False
        return self.touching()

    def home_pressed(self):
        if self.home_wire_broken:
            return True
        hyst = HOME_HYST_DEG if self._home_state else 0.0
        pressed = geo.HOME_CAM_LOW_DEG <= self.yaw <= 0.0 + hyst
        self._home_state = pressed
        return pressed

    def _track_switch(self, delta_deg):
        """The switch follows the cam as the arm moves (each move is one direction)."""
        if self.home_wire_broken:
            return
        if self.yaw < geo.HOME_CAM_LOW_DEG:
            self._home_state = False
        elif delta_deg < 0:
            self._home_state = self.yaw <= 0.0 or bool(self._home_state and self.yaw <= HOME_HYST_DEG)
        else:
            self._home_state = bool(self._home_state) and self.yaw <= HOME_HYST_DEG or (
                not self._home_state and self.yaw <= 0.0)

    def bed_grams(self):
        g = sum(self.bed)
        if self.station() == "scan" and self.touching():
            g += SLIDER_G
        return g

    # ── actuators ───────────────────────────────────────────────────────────
    def set_th(self, th):
        self.th = float(th)
        s = self.surface_z()
        if s is not None and s - self.cup_bottom_z() > geo.SLIDER_TRAVEL_MM:
            self.events.append(("crash", f"slider over-travel at {self.station()} "
                                         f"({s - self.cup_bottom_z():.1f} mm)"))
            self.th = geo.th_for_lip(s - geo.SLIDER_TRAVEL_MM + geo.CARD_T_MM * self._cards(self.cup))

    def move_yaw(self, delta_deg, low_current=False):
        if self.th < geo.TH_FULL - 1e-6:
            self.events.append(("yaw_low", self.th))
        if not self.yaw_enabled:
            self.events.append(("crash", "yaw stepped while the driver was disabled"))
        self.yaw += delta_deg + self.slip_next_deg
        self.slip_next_deg = 0.0
        self._track_switch(delta_deg)
        if self.yaw < geo.CABLE_POST_DEG:
            self.events.append(("stall", "cable post at the homing current") if low_current
                               else ("crash", "cable post"))
            self.yaw = geo.CABLE_POST_DEG

    def on_pump(self, on: bool):
        was, self.pump = self.pump, on
        if on and not was:
            name = self.station()
            pile = self._pile(name) if name else None
            if self.touching() and pile and not self.cup:
                if self.seal_fail > 0:
                    self.seal_fail -= 1
                else:
                    self.cup.append(pile.pop())
        elif was and not on and self.cup:
            if self.release_fail > 0:
                self.release_fail -= 1
                return
            card = self.cup.pop()
            name = self.station()
            s = self.surface_z()
            height = geo.lip_z(self.th) - geo.CARD_T_MM * self._cards([card]) - (s or 0.0)
            if height > DROP_OK_MM:
                self.events.append(("drop", name, round(height, 1)))
            pile = self._pile(name) if name else None
            if pile is not None:
                pile.append(card)
            else:
                self.events.append(("drop", "lost", round(height, 1)))

    def hazards(self):
        return [e for e in self.events if e[0] in ("drop", "crash", "yaw_low")]


WORLD = World()


def reset(**kw) -> World:
    """Fresh world (tests)."""
    global WORLD
    WORLD = World(**kw)
    return WORLD


def attach() -> None:
    """Wire the shared drivers' MOCK hooks to the world (vacuum, load cell)."""
    from hardware import loadcell, vacuum
    vacuum._mock_listener = lambda on: WORLD.on_pump(on)
    loadcell.mock_set_load_source(lambda: WORLD.bed_grams())
