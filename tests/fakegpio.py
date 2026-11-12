"""Minimal RPi.GPIO emulation (ported from the audit's scratch tests): pin
modes/levels, soft PWM (duty only), cleanup -> input with no pull, and
output() on a non-output channel raises RuntimeError like the real C module.
Every level change is appended to `log` so tests can replay pin states."""
BCM = 11; OUT = 0; IN = 1; HIGH = 1; LOW = 0; PUD_UP = 22; PUD_DOWN = 21; PUD_OFF = 20
mode = {}; level = {}; pud = {}; log = []
input_value = {}          # pin -> value returned by input() (default 1)


def reset():
    mode.clear(); level.clear(); pud.clear(); log.clear(); input_value.clear()


def setmode(m): pass
def setwarnings(f): pass


def setup(pin, direction, initial=None, pull_up_down=PUD_OFF):
    mode[pin] = direction
    if direction == OUT:
        level[pin] = 0 if initial is None else int(initial)
        log.append(("setup_out", pin, level[pin]))
    else:
        pud[pin] = pull_up_down


def output(pin, val):
    if mode.get(pin) != OUT:
        raise RuntimeError("The GPIO channel has not been set up as an OUTPUT")
    level[pin] = int(val); log.append(("out", pin, int(val)))


def input(pin):
    return input_value.get(pin, level.get(pin, 1))


def cleanup(pins=None):
    if pins is None: pins = list(mode)
    if isinstance(pins, int): pins = [pins]
    for p in pins:
        if p in mode:
            mode.pop(p); level.pop(p, None); pud[p] = PUD_OFF; log.append(("cleanup", p))


class PWM:
    def __init__(self, pin, f): self.pin = pin; self.dc = 0; self.running = False
    def start(self, dc): self.running = True; self.ChangeDutyCycle(dc)

    def ChangeDutyCycle(self, dc):
        self.dc = dc
        if mode.get(self.pin) == OUT:
            level[self.pin] = 1 if dc >= 100 else (0 if dc <= 0 else "pwm")
        log.append(("pwm", self.pin, dc))

    def stop(self): self.running = False
