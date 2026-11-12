"""
Single-instance lock (data/sorter.lock) and clean-shutdown marker
(data/machine_state.json), shared by main.py and the tools that drive the
machine directly (scripts/test_hardware.py, scripts/calibrate_servos.py,
scripts/calibrate_camera.py) — audit 3 M2.

Lock: an flock held for the life of the process. Only one of {the sorter
(main loop / web-only / --calibrate), any tool} runs at a time; a tool refuses
to start while the sorter runs, and the sorter refuses while a tool runs.
The lock file holds "<pid> <owner>" so the refusal can say who holds it.

Marker: {"clean": bool, "confirmed": bool, "reason": str, "rest_pose": ...}.
main.py trusts clean + rest_pose "home_level" to re-assert the rest pose
blindly at the next start (no operator confirmation). A tool therefore
writes clean=False ("tool ran: ...") BEFORE it moves anything, and never
writes it clean again: after any tool run the next sorter start asks for
"Machine clear" (the tool may have been killed, or lost power, with the
carriage at a column and the cradle tipped, or a card on the belt).

Writes are atomic (unique temp file + os.replace) and durable (the temp
file and the directory are fsynced), so a power cut right after a write
never leaves a stale "clean" record behind.

MOCK runs use their own files (machine_state.mock.json, sorter.mock.lock) so
a mock run never touches the real machine's record.
"""

import json
import os
import tempfile
import time
from pathlib import Path

try:
    import fcntl
except ImportError:          # non-POSIX dev machine
    fcntl = None

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class LockBusy(RuntimeError):
    """Another sorter process or tool holds the instance lock."""


def state_file(mock: bool) -> Path:
    return DATA_DIR / ("machine_state.mock.json" if mock else "machine_state.json")


def lock_file(mock: bool) -> Path:
    return DATA_DIR / ("sorter.mock.lock" if mock else "sorter.lock")


# ── Lock ─────────────────────────────────────────────────────────────────────
def acquire_lock(path: Path, owner: str):
    """flock `path` (non-blocking). Returns the open file handle — keep it open
    for the life of the process — or None if another process holds it.
    Without fcntl (non-POSIX) returns True (no locking)."""
    if fcntl is None:
        return True
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()} {owner}\n")
    fh.flush()
    return fh


def lock_held(path: Path) -> bool:
    """Is some process holding the lock on `path`?"""
    path = Path(path)
    if fcntl is None or not path.exists():
        return False
    with open(path, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
    return False


def lock_holder(path: Path) -> str:
    """"<pid> <owner>" written by the holder (best effort, may be empty)."""
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


# ── Marker ───────────────────────────────────────────────────────────────────
def read_state(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {"clean": False, "confirmed": False,
                "reason": "no record of a previous clean shutdown (first start?)"}
    except Exception as exc:
        return {"clean": False, "confirmed": False, "reason": f"machine state file unreadable: {exc}"}
    return {"clean": False, "confirmed": False, "reason": "machine state file invalid"}


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_state(path: Path, **fields) -> dict:
    """Atomically and durably replace the marker. Returns the record written."""
    path = Path(path)
    data = {"clean": False, "confirmed": False, "reason": "", "ts": time.time(), **fields}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(data, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(path.parent)
    return data


# ── Tools ────────────────────────────────────────────────────────────────────
TOOL_REASON = ("tool ran: {tool} drove the machine directly (it may have stopped with the "
               "carriage at a column, the cradle tipped or a card in the machine) — check the arm, "
               "belt and cradle, remove any card, then confirm")


def claim_for_tool(tool: str, mock: bool):
    """For a tool that drives the machine: take the instance lock (LockBusy if
    the sorter or another tool runs), then record the machine as NOT clean
    before anything moves. Returns the lock handle: keep a reference to it
    until the tool exits (the lock is released when the process ends)."""
    lf = lock_file(mock)
    fh = acquire_lock(lf, tool)
    if fh is None:
        holder = lock_holder(lf)
        raise LockBusy(f"the sorter or another tool is running ({lf} is locked"
                       + (f" by {holder}" if holder else "") + ") — stop it first "
                       "(sudo systemctl stop riftbound-sorter), then re-run")
    write_state(state_file(mock), clean=False, confirmed=False,
                reason=TOOL_REASON.format(tool=tool), tool=tool)
    return fh
