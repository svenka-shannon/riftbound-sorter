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

File ownership (audit 4 m2): a lock / marker this user cannot open (left
root-owned by a tool run with sudo) raises LockFileError naming the file and
the fix (`sudo chown -R <user>: data/`); main.py refuses with exit 78, which
the unit's RestartPreventExitStatus keeps from a restart loop. Run as root
anyway, the files this module creates are given to the owner of data/.

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


class LockFileError(RuntimeError):
    """The lock file (or data/) cannot be opened by this user — typically left
    root-owned by a tool run with sudo (audit 4 m2). Restarting will not fix
    it: main.py exits 78 (EX_CONFIG, in the unit's RestartPreventExitStatus)."""


EX_CONFIG = 78


def _owner_hint(path: Path) -> tuple[str, str]:
    """Who owns `path` / the user to give it back to, for the error message."""
    try:
        import pwd
        st = Path(path).stat()
        owner = pwd.getpwuid(st.st_uid).pw_name
        me = pwd.getpwuid(os.geteuid()).pw_name
        return f" (owned by {owner}, this process runs as {me})", me
    except Exception:
        return "", os.environ.get("USER", "pi")


def lock_file_error(path: Path, exc: BaseException) -> LockFileError:
    """LockFileError naming the file and the fix (chown)."""
    path = Path(path)
    owned, me = _owner_hint(path if path.exists() else path.parent)
    return LockFileError(
        f"cannot open {path}{owned}: {exc}. It was probably created by a "
        f"hardware tool run with sudo. Fix: sudo chown -R {me}: {path.parent} — and never run "
        "the tools (test_hardware.py, calibrate_servos.py, calibrate_camera.py) or main.py "
        "with sudo")


def _match_parent_owner(path: Path) -> None:
    """Run as root (a tool started with sudo despite the docs): give a file we
    just created in data/ to the owner of its directory, so the service user
    can still open it (audit 4 m2). No-op for a normal user."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    try:
        st = Path(path).parent.stat()
        if st.st_uid != 0:
            os.chown(path, st.st_uid, st.st_gid)
    except OSError:
        pass


def _mkdir(directory: Path) -> None:
    """mkdir -p; a directory root creates is given to its parent's owner."""
    directory = Path(directory)
    if directory.exists():
        return
    directory.mkdir(parents=True, exist_ok=True)
    _match_parent_owner(directory)


def data_dir_problems(lock_path: Path) -> list[str]:
    """Start-up check (audit 4 m2): what this process must be able to write in
    data/ — the instance lock, and its directory (the clean-shutdown marker is
    replaced atomically there). One line per problem, each naming the file and
    the chown fix; empty if all is well (or the files do not exist yet)."""
    lock_path = Path(lock_path)
    problems = []
    for path, mode in ((lock_path.parent, os.W_OK | os.X_OK), (lock_path, os.R_OK | os.W_OK)):
        if path.exists() and not os.access(path, mode):
            owned, me = _owner_hint(path)
            problems.append(f"{path} is not writable by this user{owned} — left by a tool run "
                            f"with sudo? Fix: sudo chown -R {me}: {lock_path.parent}")
    return problems


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
    try:
        _mkdir(path.parent)
        created = not path.exists()
        fh = open(path, "a+")
    except OSError as exc:
        # e.g. a root-owned lock left by `sudo scripts/test_hardware.py`: refuse
        # cleanly (main.py exits 78) instead of crashing into a restart loop
        raise lock_file_error(path, exc) from exc
    if created:
        _match_parent_owner(path)
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
    """Is some process holding the lock on `path`? (Opens it read-only: an
    flock works on any descriptor, so a lock file this user cannot write
    still answers. LockFileError if it cannot be opened at all.)"""
    path = Path(path)
    if fcntl is None or not path.exists():
        return False
    try:
        fh = open(path, "r")
    except OSError as exc:
        raise lock_file_error(path, exc) from exc
    with fh:
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


def fsync_dir(directory: Path) -> None:
    """fsync a directory so a rename in it is durable (best effort)."""
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
    _mkdir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(data, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        _match_parent_owner(tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    fsync_dir(path.parent)
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
    try:
        write_state(state_file(mock), clean=False, confirmed=False,
                    reason=TOOL_REASON.format(tool=tool), tool=tool)
    except OSError as exc:
        raise lock_file_error(state_file(mock), exc) from exc
    return fh
