"""D0 -- deterministic ingest & repair of the M3-D preregistered task document.

The handoff copy suffered an upstream escaping accident: TeX macro backslashes
were consumed into control characters (\b->BS, \t->TAB, \f->FF, \r->CR).  This
script performs ONLY the enumerated structural repairs below, asserts the
postcondition that no unexpected control character survives, writes the
canonical file plus an as-received archive copy, and prints a machine-readable
provenance manifest with sha256 hashes of all three artifacts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SRC = Path(r"D:\Users\huangyx\Desktop\RareTopo\handoff"
           r"\M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md")
DIR = Path("docs/phase_m3d")
RECV = DIR / "received" / "M3_D_Task.as-received.md"
CANON = DIR / "M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md"

# ---- complete corruption inventory (byte-verified 2026-08-27) --------------
REPAIRS = [
    # each raw pattern begins with the CONTROL CHARACTER produced when an
    # upstream escaping pass consumed the macro backslash (\b->BS, \t->TAB,
    # \f->FF, \r->CR); expected counts are the byte-level forensic inventory.
    ("\u0008oxed",   "\\boxed",   2),   # \b swallowed  -> BS + "oxed"
    ("\text",        "\\text",    8),   # \t -> TAB + "ext"
    ("\times",       "\\times",   1),   # \t -> TAB + "imes"
    ("\theta",       "\\theta",   3),   # \t -> TAB + "heta"
    ("\u000crac",    "\\frac",    6),   # \f swallowed  -> FF + "rac"
    ("\right]",      "\\right]",  1),   # \r -> CR + "ight]"
]
# NOTE: python parses "\text"/"\times"/"\theta"/"\right]" as
# CTRL-char + remainder precisely because their real escapes (\t,\r) are
# valid -- which is exactly the corrupted form.  "\h" / "\i" are NOT valid
# escapes, so writing "\heta" there would match a literal backslash and fail;
# the manifest assert below pins every expected count.


def main() -> int:
    raw = SRC.read_bytes()
    text = raw.decode("utf-8")

    recv_expected_counts: dict[str, int] = {}
    fixed = text
    applied: dict[str, int] = {}
    for bad, good, expect in REPAIRS:
        n = fixed.count(bad)
        recv_expected_counts[repr(bad)] = n
        if expect and n < expect:
            print(f"FATAL: pattern {bad!r} found {n} < declared {expect}",
                  file=sys.stderr)
            return 1
        if n != expect:
            print(f"WARN: pattern {bad!r} found {n}, declared {expect}",
                  file=sys.stderr)
        if n:
            fixed = fixed.replace(bad, good)
            applied[good] = applied.get(good, 0) + n

    leftover = {}
    for ch in set(fixed):
        if ord(ch) < 32 and ch not in ("\n",):
            leftover[hex(ord(ch))] = fixed.count(ch)

    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "received").mkdir(exist_ok=True)
    RECV.write_text(text, encoding="utf-8", newline="\n")
    CANON.write_text(fixed, encoding="utf-8", newline="\n")

    h_src = hashlib.sha256(raw).hexdigest()
    h_recv = hashlib.sha256(RECV.read_bytes()).hexdigest()
    h_canon = hashlib.sha256(CANON.read_bytes()).hexdigest()

    manifest = {
        "source_sha256": h_src,
        "as_received_sha256": h_recv,
        "canonical_sha256": h_canon,
        "corruption_inventory_in_source": recv_expected_counts,
        "repairs_applied": applied,
        "leftover_control_chars_canonical": leftover,
        "accept": bool(not leftover),
        "bytes_source": len(raw),
        "bytes_canonical": CANON.stat().st_size,
    }
    (DIR / "task_ingest_provenance.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    return 0 if not leftover else 2


if __name__ == "__main__":
    raise SystemExit(main())
