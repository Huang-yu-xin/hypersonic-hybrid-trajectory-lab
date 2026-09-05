"""M3-PI1VR0 fresh-panel contracts (conditional on capacity PASS)."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1vr0 as R  # noqa: E402

OUT = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def capacity():
    return load(OUT / "m3pi1vr0_fresh_panel_capacity.json")


def _panel_rows_if_any():
    p = OUT / "m3pi1vr0_fresh_development_panel.csv"
    return csv_rows(p) if p.exists() else None


def test_m3pi1vr0_fresh_panel_exact24():
    rows = _panel_rows_if_any()
    if capacity()["FRESH_PANEL_CAPACITY"] == "FAIL":
        assert rows is None                      # explicitly not created
        assert capacity()["fresh_development_panel_created"] is False
        return
    assert rows is not None and len(rows) == 24


def test_m3pi1vr0_fresh_panel_8w8s8nd():
    rows = _panel_rows_if_any()
    if capacity()["FRESH_PANEL_CAPACITY"] == "FAIL":
        # the binding shortage is documented, never relaxed
        assert capacity()["binding_shortage"]
        assert capacity()["counts_relaxed_after_shortage"] is False
        return
    from collections import Counter
    grp = Counter("W" if r["truth"] == "WIDEN" else "S" if r["truth"] == "SHRINK"
                  else "ND" for r in rows)
    assert grp == {"W": 8, "S": 8, "ND": 8}


def test_m3pi1vr0_fresh_panel_unique():
    rows = _panel_rows_if_any()
    if rows is None:
        return
    assert len({r["state_id"] for r in rows}) == len(rows)


def test_m3pi1vr0_fresh_panel_pilot_zero():
    rows = _panel_rows_if_any()
    if rows is None:
        audit = {r["state_id"]: r for r in csv_rows(
            OUT / "m3pi1vr0_reserve_exposure_audit.csv")}
        assert all(int(r["gradient_exposure"]) == 0 for r in audit.values())
        return
    assert all(int(r.get("gradient_exposure", 0)) == 0 for r in rows)


def test_m3pi1vr0_fresh_panel_probe_zero():
    rows = _panel_rows_if_any()
    if rows is None:
        audit = {r["state_id"]: r for r in csv_rows(
            OUT / "m3pi1vr0_reserve_exposure_audit.csv")}
        assert all(int(r["probe_exposure"]) == 0 for r in audit.values())
        return
    assert all(int(r.get("probe_exposure", 0)) == 0 for r in rows)


def test_m3pi1vr0_selector_deterministic():
    view = csv_rows(OUT / "m3pi1vr0_selection_view.csv")
    # S and ND selections succeed deterministically; W deterministically fails
    # (capacity shortage) with the identical error on every run
    s1 = R._run_selector.__wrapped__ if hasattr(R._run_selector, "__wrapped__") \
        else None
    from collections import Counter
    s_pool = [r for r in view if r["truth"] == "SHRINK"]
    nd_pool = [r for r in view if r["truth"] in ("HOLD", "AMBIGUOUS")]
    w_pool = [r for r in view if r["truth"] == "WIDEN"]

    def pick8(states):
        chosen = []
        pool = sorted(states, key=lambda s: (int(s["canonical_bank_order"]),
                                             s["state_id"]))
        while len(chosen) < 8 and pool:
            used_cfg = Counter(c["config_id"] for c in chosen)
            used_region = Counter(c["source_region"] for c in chosen)
            candidates = [s for s in pool if used_cfg[s["config_id"]] < 2]
            if not candidates:
                raise RuntimeError("selector: diversity constraint infeasible")
            best = min(candidates, key=lambda s: (
                used_cfg[s["config_id"]], used_region[s["source_region"]],
                min((abs(float(s["s2"]) - float(c["s2"])) for c in chosen),
                    default=float("inf")),
                int(s["canonical_bank_order"]), s["state_id"]))
            chosen.append(best)
            pool.remove(best)
        if len(chosen) != 8:
            raise RuntimeError("selector: shortfall")
        return chosen

    assert pick8(s_pool) == pick8(s_pool)
    assert pick8(nd_pool) == pick8(nd_pool)
    try:
        pick8(w_pool)
        feasible_w = True
    except RuntimeError:
        feasible_w = False
    assert feasible_w == capacity()["feasibility"]["W_diversity_feasible"]


def test_m3pi1vr0_no_manual_override():
    contract = load(OUT / "m3pi1vr0_selector_contract.json")
    assert contract["deterministic"] is True
    assert contract["manual_override"] == "FORBIDDEN"
    assert contract["input"].startswith("redacted selection view only")


def test_m3pi1vr0_remaining_reserve_protected():
    rows = csv_rows(OUT / "m3pi1vr0_remaining_reserve_manifest.csv")
    reserve = csv_rows(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    assert {r["state_id"] for r in rows} == {r["state_id"] for r in reserve}
    assert all(r["status"] == "PILOT_PROTECTED_RESERVE" for r in rows)
    summary = load(OUT / "m3pi1vr0_remaining_reserve_summary.json")
    assert summary["pilot_exposure"] == 0
    assert summary["remaining_protected_states"] == \
        sum(1 for r in rows if r["consumed_by_fresh_panel"] == "False")


def test_m3pi1vr0_fresh_panel_hash():
    hp = OUT / "m3pi1vr0_fresh_panel_hash.json"
    if capacity()["FRESH_PANEL_CAPACITY"] == "FAIL":
        assert not hp.exists()
        assert not (OUT / "m3pi1vr0_fresh_development_panel.csv").exists()
        return
    import hashlib
    rec = load(hp)
    digest = hashlib.sha256(
        (OUT / "m3pi1vr0_fresh_development_panel.csv").read_bytes()).hexdigest()
    assert rec["panel_sha256"] == digest
