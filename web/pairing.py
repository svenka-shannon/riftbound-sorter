"""
"Pair this phone": a one-time pairing code that hands the web UI token to a
phone without the token ever being printed, logged or sent over a GET.

  1. On the Pi (SSH, as the user the service runs as):
       python main.py --pair
     prints a 6-digit code, valid PAIR_TTL_S (10 min), single use. The code
     is stored only as a salted SHA-256 in config/web_pair.json (mode 600,
     next to config/web.json), so it is never in the journal either.
  2. In the phone app: Pair → type the code. POST /api/pair {"code": ...}
     answers {"token": ...} once; the app keeps the token in localStorage.

Rules:
  * single use: the file is deleted BEFORE the token is returned; if the
    service cannot delete it (e.g. it was written by root), pairing is
    refused, never answered twice;
  * PAIR_MAX_ATTEMPTS (5) wrong codes invalidate the code;
  * expired / missing code → refused (401) like a wrong one.
The alternative stays: type the token itself (`python main.py --web-token`),
which the app checks with POST /api/auth/check.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

PAIR_TTL_S = 600.0
PAIR_MAX_ATTEMPTS = 5
CODE_DIGITS = 6

_lock = threading.Lock()


class PairingError(Exception):
    """Pairing refused; .status is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def pair_file(web_config_file: Path) -> Path:
    """config/web_pair.json, next to the token file (tests redirect both)."""
    return Path(web_config_file).with_name("web_pair.json")


def _digest(salt: str, code: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
    except (AttributeError, OSError):
        pass
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def create_code(path: Path, now: float | None = None) -> str:
    """New pairing code (replaces any earlier one). Returns the code."""
    now = time.time() if now is None else now
    code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
    salt = secrets.token_hex(8)
    _write(Path(path), {"salt": salt, "digest": _digest(salt, code),
                        "expires": now + PAIR_TTL_S, "attempts": 0})
    return code


def _normalise(code) -> str:
    return "".join(ch for ch in str(code or "") if ch.isdigit())


def redeem(path: Path, code, now: float | None = None) -> None:
    """Check `code` against the pending pairing code and consume it.
    Returns normally on success (the caller then hands out the token);
    raises PairingError otherwise."""
    path = Path(path)
    now = time.time() if now is None else now
    code = _normalise(code)
    if len(code) != CODE_DIGITS:
        raise PairingError(f"the pairing code has {CODE_DIGITS} digits", 400)
    with _lock:
        try:
            data = json.loads(path.read_text())
        except FileNotFoundError:
            raise PairingError("no pairing code is active — run `python main.py --pair` on the Pi")
        except (OSError, ValueError):
            raise PairingError("pairing file unreadable — run `python main.py --pair` again "
                               "(as the user the sorter service runs as)", 500)
        try:
            expired = now > float(data["expires"])
            ok = hmac.compare_digest(_digest(str(data["salt"]), code), str(data["digest"]))
            attempts = int(data.get("attempts", 0))
        except (KeyError, TypeError, ValueError):
            expired, ok, attempts = True, False, PAIR_MAX_ATTEMPTS
        if expired or attempts >= PAIR_MAX_ATTEMPTS:
            _discard(path)
            raise PairingError("pairing code expired or used up — run `python main.py --pair` again")
        if not ok:
            data["attempts"] = attempts + 1
            try:
                if data["attempts"] >= PAIR_MAX_ATTEMPTS:
                    path.unlink()
                else:
                    _write(path, data)
            except OSError:
                raise PairingError("pairing file not writable by the sorter service — run "
                                   "`python main.py --pair` as the service's user", 500)
            left = PAIR_MAX_ATTEMPTS - data["attempts"]
            raise PairingError("wrong pairing code" + (f" ({left} tries left)" if left else
                                                        " — code invalidated, make a new one"))
        try:
            path.unlink()                  # consume BEFORE answering: never valid twice
        except OSError:
            raise PairingError("pairing file not removable by the sorter service — run "
                               "`python main.py --pair` as the service's user", 500)


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
