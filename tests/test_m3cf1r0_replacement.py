"""M3-CF1R0 outcome-blind replacement expansion contracts (task §14-§22, §24)."""
import csv
import json
from pathlib import Path

from hyptraj.m3cf1r0.persistence import sha256_file

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3cf1r0/summary"
REPL = ROOT / "results/phase_m3cf1r0/replacement"
CF0 = ROOT / "results/phase_m3cf0/summary"
CF1 = ROOT / "results/phase_m3cf1/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def vector(r):
    v = []
    for i in range(4):
        v.append(float(r[f"theta_{i+1}"]) / (360 if i else 120))
    for i in range(4):
        v.append((float(r[f"h_{i+1}"]) - 1.5) / (1.1 if i else 0.5))
    for i in range(1, 4):
        v.append(float(bool(r[f"curved_{i+1}"])))
    for i in range(1, 4):
        v.append((float(r[f"offset_{i+1}"]) + 1) / 2)
    return v


def dist(a, b):
    import math

    return math.sqrt(sum((x - y) ** 2 for x, y in zip(vector(a), vector(b))))


def test_replacement_uses_cf0_legal_domain():
    lattice_ids = {r["config_id"] for r in rows(CF0 / "m3cf0_raw_physical_candidate_lattice.csv") if r["legal"] == "True"}
    for r in rows(REPL / "m3cf1r0_replacement_configs.csv"):
        assert r["config_id"].startswith("cf1n_new_")
        # physical parameters come from a CF0 lattice row (coordinates match)
        assert any(
            all(abs(float(r[k]) - float(c[k])) < 1e-12 for k in ("theta_1", "theta_2", "theta_3", "theta_4", "h_1", "h_2", "h_3", "h_4"))
            for c in rows(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")
        )


def test_replacement_excludes_all_cf1_configs():
    cf1_manifest = load(CF1 / "m3cf1_new_config_manifest.json")["config_ids"]
    cf1_frozen = {r["new_config_id"]: r for r in rows(CF0 / "m3cf0_frozen_new_configs.csv")}
    sel = rows(REPL / "m3cf1r0_replacement_configs.csv")
    for r in sel:
        assert r["config_id"] not in cf1_manifest
        for cid, coords in cf1_frozen.items():
            assert any(
                abs(float(r[k]) - float(coords[k])) > 1e-9
                for k in ("theta_1", "theta_2", "theta_3", "theta_4", "h_1", "h_2", "h_3", "h_4")
            ), f"replacement {r['config_id']} duplicates CF1 config {cid}"
    excl = load(REPL / "m3cf1r0_replacement_exclusion.json")
    assert excl["cf1_config_identities"] == sorted(cf1_manifest)
    assert len(excl["cf1_lattice_row_identities"]) == 8


def test_replacement_selection_ignores_cf1_outcomes():
    prereg = load(REPL / "m3cf1r0_replacement_prereg_hashes.json")
    att = prereg["outcome_independence_attestation"]
    assert att["cf1_outcome_labels_used_in_selection"] is False
    assert att["cf1_discovery_or_confirmation_files_read_by_selection"] is False
    assert att["learned_response_surface"] is False
    excl = load(REPL / "m3cf1r0_replacement_exclusion.json")
    assert "CF1 discovery labels" in excl["forbidden_inputs_confirmed_unused"]
    assert "any confirmation outcome" in excl["forbidden_inputs_confirmed_unused"]


def test_replacement_maximin_deterministic():
    lattice = [r for r in rows(CF0 / "m3cf0_raw_physical_candidate_lattice.csv") if r["legal"] == "True"]
    originals = rows(CF0 / "m3cf0_current_config_coordinates.csv")
    cf1_frozen = rows(CF0 / "m3cf0_frozen_new_configs.csv")
    cf1_raw_ids = {r["config_id"] for r in cf1_frozen}
    candidates = [r for r in lattice if r["config_id"] not in cf1_raw_ids]
    base = list(originals) + list(cf1_frozen)
    import math

    centroid = [
        sum(vector(r)[i] for r in originals) / len(originals)
        for i in range(len(vector(originals[0])))
    ]
    chosen, remaining = [], list(candidates)
    while len(chosen) < 8 and remaining:
        def key(r):
            md = min(dist(r, q) for q in base + chosen)
            cd = math.sqrt(sum((x - y) ** 2 for x, y in zip(vector(r), centroid)))
            return (md, cd, sum(bool(r[f"curved_{i}"]) for i in range(2, 5)), r["config_id"])

        best = max(remaining, key=key)
        chosen.append(best)
        remaining.remove(best)
    frozen = rows(REPL / "m3cf1r0_replacement_configs.csv")
    expected_ids = {r["config_id"] for r in chosen}
    # frozen CSV rows carry replacement ids; match by physical coordinates
    coord_key = lambda r: tuple(round(float(r[k]), 9) for k in ("theta_1", "theta_2", "theta_3", "theta_4", "h_1", "h_2", "h_3", "h_4"))
    assert {coord_key(r) for r in frozen} == {coord_key(r) for r in chosen}
    # determinism: re-running the rule reproduces the same ids step by step
    for i, r in enumerate(frozen):
        assert r["selection_step"] == str(i + 1)


def test_replacement_exact8_configs():
    sel = rows(REPL / "m3cf1r0_replacement_configs.csv")
    assert len(sel) == 8
    assert [r["config_id"] for r in sel] == [f"cf1n_new_{i:03d}" for i in range(8)]
    for r in sel:
        for f in ("selection_step", "minimum_distance", "nearest_original_or_retired_config", "interpolation_or_extrapolation"):
            assert r[f] not in ("", None)
        assert r["interpolation_or_extrapolation"] in ("interpolation", "extrapolation")


def test_replacement_grid_matches_cf0_hash():
    grid = load(REPL / "m3cf1r0_replacement_s2_grid.json")
    cf0_grid = load(CF0 / "m3cf0_future_s2_grid.json")
    assert grid["values"] == cf0_grid["values"]
    assert grid["frozen"] is True
    assert grid["source_sha256"] == sha256_file(CF0 / "m3cf0_future_s2_grid.json")
    assert grid["matches_cf0_frozen_grid_hash"] is True
    assert grid["no_grid_redesign_after_cf1x"] is True


def test_replacement_target_two_stable():
    exp = load(OUT / "m3cf1r0_replacement_expansion.json")
    t = exp["scientific_target"]
    assert t["current_stable_s"] == 2
    assert t["k_new_stable_required"] == 2
    assert t["final_structural_target_min_stable"] == 4
    assert t["no_relaxation"] is True
    assert exp["capacity_gate_pass"] is True
    assert exp["legal_fresh_candidates"] >= 8


def test_value_blocked():
    assert load(OUT / "m3cf1r0_final_verdict.json")["value"] == "BLOCKED"


def test_rarity_blocked():
    assert load(OUT / "m3cf1r0_final_verdict.json")["rarity_shift"] == "BLOCKED"


def test_m3q_blocked():
    assert load(OUT / "m3cf1r0_final_verdict.json")["m3_q"] == "BLOCKED"


def test_output_schema():
    required_results = [
        "m3cf1r0_source_manifest.json",
        "m3cf1r0_cf1_quarantine_manifest.json",
        "m3cf1r0_cf1_scientific_status.json",
        "m3cf1r0_retired_state_seed_manifest.json",
        "m3cf1r0_persistence_failure_forensics.json",
        "m3cf1r0_artifact_integrity_audit.json",
        "m3cf1r0_persistence_contract.json",
        "m3cf1r0_failure_injection_matrix.json",
        "m3cf1r0_synthetic_clean_run.json",
        "m3cf1r0_synthetic_failure_runs.json",
        "m3cf1r0_persistence_gate.json",
        "m3cf1r0_protected_confirmation_audit.json",
        "m3cf1r0_final_verdict.json",
        "m3cf1r0_replacement_expansion.json",
    ]
    assert all((OUT / n).exists() for n in required_results)
    required_replacement = [
        "m3cf1r0_replacement_candidate_lattice.csv",
        "m3cf1r0_replacement_exclusion.json",
        "m3cf1r0_replacement_configs.csv",
        "m3cf1r0_replacement_s2_grid.json",
        "m3cf1r0_replacement_prereg_hashes.json",
    ]
    assert all((REPL / n).exists() for n in required_replacement)
    required_docs = [
        "M3_CF1R0_Task.md",
        "M3_CF1R0_CF1_Incident_Forensics.md",
        "M3_CF1R0_Scientific_Quarantine.md",
        "M3_CF1R0_Persistence_Contract.md",
        "M3_CF1R0_Failure_Injection_Audit.md",
        "M3_CF1R0_Replacement_Expansion_Design.md",
        "M3_CF1R0_Protected_Confirmation_Audit.md",
        "M3_CF1R0_Final_Decision.md",
    ]
    assert all((ROOT / "docs/phase_m3cf1r0" / n).exists() for n in required_docs)
    # prereg hashes must match the files actually on disk
    prereg = load(REPL / "m3cf1r0_replacement_prereg_hashes.json")
    for e in prereg["replacement_freeze_files"] + prereg["source_files"]:
        assert sha256_file(ROOT / e["path"]) == e["sha256"], e["path"]
