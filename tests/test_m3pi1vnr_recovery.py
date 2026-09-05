"""M3-PI1VNR retirement/quarantine + fresh-panel contracts (taskbook Sec. 39)."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vnr/summary"
CFG = ROOT / "configs/phase_m3pi1vnr"
PI1VN = ROOT / "results/phase_m3pi1vn"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


# ------------------------- retirement / quarantine -------------------------

def test_m3pi1vnr_parent_pi1vn_x():
    assert load(PI1VN / "summary/m3pi1vn_final_verdict.json")["verdict"] == "PI1VN-X"
    st = load(OUT / "m3pi1vnr_pi1vn_incident_status.json")
    assert st["PI1VN valid verdict"] == "PI1VN-X"
    assert st["PI1VN primary V1 result"] == "UNAVAILABLE"


def test_m3pi1vnr_pi1vn_primary_unavailable():
    st = load(OUT / "m3pi1vnr_pi1vn_incident_status.json")
    assert st["PI1VN primary V1 result"] == "UNAVAILABLE"
    assert st["PI1VN primary S1 result"] == "UNAVAILABLE"
    assert st["PI1VN direction result"] == "UNAVAILABLE"
    assert st["136 durable completed trials"] == "DIAGNOSTIC_ONLY"


def test_m3pi1vnr_all24_pi1vn_panel_retired():
    rows = csv_rows(OUT / "m3pi1vnr_retired_pi1vn_panel.csv")
    pi1vn_panel = csv_rows(PI1VN / "summary/../summary/m3pi1vn_final_verdict.json") \
        if False else None
    import csv as _csv
    with (ROOT / "results/phase_m3wcf1/summary/m3wcf1_fresh_development_panel.csv"
          ).open(newline="", encoding="utf-8") as h:
        old = {r["state_id"] for r in _csv.DictReader(h)}
    assert len(rows) == 24 and {r["state_id"] for r in rows} == old
    assert all(r["status"] == "PILOT_EXPOSED_RETIRED" for r in rows)
    assert all(r["future_development_use"] == "NO" for r in rows)


def test_m3pi1vnr_no_pi1vn_panel_reuse():
    retired = {r["state_id"] for r in csv_rows(OUT / "m3pi1vnr_retired_pi1vn_panel.csv")}
    panel = {r["state_id"] for r in csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")}
    assert panel & retired == set()


def test_m3pi1vnr_all_pi1vn_seeds_retired():
    ret = load(OUT / "m3pi1vnr_retired_pi1vn_seed_manifest.json")
    assert ret["retired_namespaces"] == ["M3-PI1VN-GRAD", "M3-PI1VN-PROBE"]
    assert ret["includes_never_started_trials"] is True
    seeds = load(OUT / "m3pi1vnr_seed_manifest.json")
    ret_vals = set(ret["gradient_seeds"].values()) | \
        set(ret["probe_seeds"].values())
    for v in seeds["planned_gradient_seeds"].values():
        assert v not in ret_vals
    for v in seeds["planned_probe_seeds"].values():
        assert v not in ret_vals


def test_m3pi1vnr_no_partial_pi1vn_metrics_used():
    qm = load(OUT / "m3pi1vnr_pi1vn_quarantine_manifest.json")
    assert qm["scientific_use"] == "diagnostic only"
    assert "never used for thresholds, verdicts, or routes" in qm["scientific_use_rule"]
    # the PI1VN partial outputs were never a design input: the selection view
    # carries no score fields at all
    header = (OUT / "m3pi1vnr_selection_view.csv").read_text(encoding="utf-8").splitlines()[0]
    for tok in ("V1", "S1", "r_hat", "SE"):
        assert tok not in header


def test_m3pi1vnr_no_invalid_pi1v_metrics_used():
    st = load(OUT / "m3pi1vnr_pi1vn_incident_status.json")
    assert "no numerical diagnostic result from PI1VN" in st["no_diagnostic_in_design_rule"]
    sel = load(OUT / "m3pi1vnr_selection_view_hash.json")
    assert sel["frozen_before_panel_selection"] is True


# ------------------------------ fresh panel --------------------------------

def test_m3pi1vnr_zero_new_reference():
    sm = load(OUT / "m3pi1vnr_source_manifest.json")
    assert sm["new_reference_samples"] == 0
    ac = load(OUT / "m3pi1vnr_sample_accounting_prereg.json")
    assert ac["new_reference_samples"] == 0


def test_m3pi1vnr_selection_view_redacted():
    rows = csv_rows(OUT / "m3pi1vnr_selection_view.csv")
    allowed = {"state_id", "truth", "config_id", "physical_family", "s2",
               "source_stage", "source_region", "stable_config_flag",
               "canonical_bank_order"}
    assert set(rows[0]) == allowed


def test_m3pi1vnr_exact8w8s8nd():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    tru = Counter(r["truth"] for r in rows)
    assert len(rows) == 24 and tru["WIDEN"] == 8 and tru["SHRINK"] == 8 \
        and tru["HOLD"] + tru["AMBIGUOUS"] == 8


def test_m3pi1vnr_w_configs_ge6():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    w = {r["config_id"] for r in rows if r["truth"] == "WIDEN"}
    assert len(w) >= 6


def test_m3pi1vnr_w_max2_per_config():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    cfg = Counter(r["config_id"] for r in rows if r["truth"] == "WIDEN")
    assert max(cfg.values()) <= 2


def test_m3pi1vnr_s_configs_ge6():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    s = {r["config_id"] for r in rows if r["truth"] == "SHRINK"}
    assert len(s) >= 6


def test_m3pi1vnr_s_max2_per_config():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    cfg = Counter(r["config_id"] for r in rows if r["truth"] == "SHRINK")
    assert max(cfg.values()) <= 2


def test_m3pi1vnr_nd_diversity():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    nd = [r for r in rows if r["truth"] in ("HOLD", "AMBIGUOUS")]
    cfgs = {r["config_id"] for r in nd}
    regions = {r["source_region"] for r in nd}
    assert len(cfgs) >= 6 or len(regions) >= 6


def test_m3pi1vnr_panel_unique():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    assert len({r["state_id"] for r in rows}) == 24


def test_m3pi1vnr_panel_pilot_zero():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    assert all(int(r["pilot_exposure"]) == 0 for r in rows)


def test_m3pi1vnr_panel_probe_zero():
    rows = csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")
    assert all(int(r["probe_exposure"]) == 0 for r in rows)


def test_m3pi1vnr_panel_hash():
    import hashlib
    rec = load(OUT / "m3pi1vnr_fresh_development_panel_hash.json")
    digest = hashlib.sha256(
        (OUT / "m3pi1vnr_fresh_development_panel.csv").read_bytes()).hexdigest()
    assert rec["panel_sha256"] == digest


def test_m3pi1vnr_remaining_reserve_protected():
    rem = csv_rows(OUT / "m3pi1vnr_remaining_protected_reserve.csv")
    panel = {r["state_id"] for r in csv_rows(OUT / "m3pi1vnr_fresh_development_panel.csv")}
    assert all(r["status"] == "PILOT_PROTECTED_RESERVE" for r in rem)
    assert not (panel & {r["state_id"] for r in rem})
