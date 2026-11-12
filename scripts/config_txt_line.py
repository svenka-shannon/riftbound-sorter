#!/usr/bin/env python3
"""
Idempotently add a line to the Raspberry Pi's config.txt (used by
scripts/setup.sh; standard library only, run as root).

  config_txt_line.py "gpio=17,27=ip,pu" [--comment TEXT] [--file PATH]

Location: /boot/firmware/config.txt (Bookworm, trixie) or /boot/config.txt
(older images); a stub that says "DO NOT EDIT" is skipped. If the exact line
is already there (not commented out, under an [all] section or before any
section filter) nothing changes and it prints "unchanged". Otherwise it is
appended at the end under its own "[all]" filter — so a model filter such as
[cm4] / [pi5] earlier in the file can never swallow it — with an optional
"# ..." comment above it, and prints "updated <path>". A copy of the original
is kept as config.txt.riftbound.bak the first time. Writes are durable like
cmdline_param.py (fsynced temp file, rename, fsynced directory: the FAT boot
partition must never be left with a half-written config.txt). A reboot
applies it. A --file that does not exist, a file that is not UTF-8 text or one
that cannot be read / written is reported in one line (exit 1, nothing
changed), never with a traceback.

Why (audit 4 m9) — "gpio=17,27=ip,pu": GPIO 17 (pump relay IN) and 27 (vent
valve relay IN) come out of reset as inputs with the SoC's default ~50 kΩ
pull-DOWN, which fights the board's external 10 kΩ pull-up: IN sits at about
3.3 V × 50 / (50 + 10) ≈ 2.75 V until something drives the pin. The config.txt
`gpio` directive (Raspberry Pi firmware, documented in "config.txt → GPIO
control": pins `17,27`, attributes `ip` input, `pu` pull up) makes the
firmware switch the internal pull to UP, so IN then sits at the full 3.3 V
(relay certainly released). It acts a few seconds after power-on (when the
firmware reads config.txt, before Linux), not from the first instant, and the
kernel / pinctrl can change it later (the sorter drives both pins as outputs
anyway, scripts/safe_outputs.py drives them HIGH after every stop).
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cmdline_param import write_durably  # noqa: E402  (same directory, standard library only)

CANDIDATES = (Path("/boot/firmware/config.txt"), Path("/boot/config.txt"))


def find_config(candidates=CANDIDATES):
    for p in candidates:
        try:
            raw = p.read_bytes()        # bytes: a non-UTF-8 file is reported by ensure_line
        except OSError:
            continue
        if b"DO NOT EDIT" in raw:
            continue
        return p
    return None


def has_line(text: str, line: str) -> bool:
    """`line` present and active: not commented out, and in effect for every
    model — before any [filter] or after an [all]."""
    section_all = True
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            section_all = s.lower() == "[all]"
            continue
        if s == line and section_all:
            return True
    return False


def updated(text: str, line: str, comment: str = "") -> str:
    if has_line(text, line):
        return text
    out = text if (not text or text.endswith("\n")) else text + "\n"
    out += "\n[all]\n"
    if comment:
        out += f"# {comment}\n"
    return out + line + "\n"


def ensure_line(path: Path, line: str, comment: str = "") -> bool:
    """True if the file was changed."""
    raw = path.read_bytes()
    text = raw.decode()
    new = updated(text, line, comment)
    if new == text:
        return False
    backup = path.with_name(path.name + ".riftbound.bak")
    if not backup.exists():
        write_durably(backup, raw)
        shutil.copystat(path, backup)
    write_durably(path, new.encode())
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="add a config.txt line idempotently")
    ap.add_argument("line", help='e.g. "gpio=17,27=ip,pu"')
    ap.add_argument("--comment", default="", help="comment written above the line")
    ap.add_argument("--file", type=Path, help="config.txt to edit (default: auto-detect)")
    args = ap.parse_args(argv)
    line = args.line.strip()
    if not line or line.startswith(("#", "[")) or "\n" in line:
        ap.error("line must be a single config.txt setting")
    path = args.file or find_config()
    if path is None:
        print("config.txt not found in " + ", ".join(map(str, CANDIDATES)), file=sys.stderr)
        return 1
    if not path.is_file():
        what = "not a regular file" if path.exists() else "no such file"
        print(f"{path}: {what} — nothing changed (check --file)", file=sys.stderr)
        return 1
    try:
        changed = ensure_line(path, line, args.comment)
    except UnicodeDecodeError as exc:
        print(f"{path} is not UTF-8 text ({exc.reason} at byte {exc.start}) — nothing changed; "
              "is it really config.txt?", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"cannot update {path}: {exc} — nothing changed (run it as root, like setup.sh)",
              file=sys.stderr)
        return 1
    print(f"updated {path}" if changed else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
