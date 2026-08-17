"""Build the Phase-F production regression snapshot (F7A §24).

Reads the corrected canonical artifacts and writes
``tests/data/phase_f_gamma_k_sensitivity_v1.json``.  The snapshot stores
stable canonical summaries and key anchors only (never the full 1089 map
or the 5735 boxes).
"""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COARSE = ROOT / "results/gamma_k_sensitivity/coarse_map"
REFINE = ROOT / "results/gamma_k_sensitivity/boundary_refinement"
FD = ROOT / "results/gamma_k_sensitivity/fd_convergence"
F5 = ROOT / "results/gamma_k_sensitivity/structural_sensitivity"
F6 = ROOT / "results/gamma_k_sensitivity/comparison_surfaces"
AUDIT = ROOT / "results/gamma_k_sensitivity/final_audit"
OUT = ROOT / "tests/data/phase_f_gamma_k_sensitivity_v1.json"

COMMITS = {
    "phase_e_anchor": "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
    "f0": "1cd0bd52de0d9cec615635949d2805525619d370",
    "f01": "81b3a9980c0df548786db4145f4e01c917cba1e4",
    "f1": "417b2a46cd9e3e621a4914f35f531ef7f0a092f4",
    "f21": "6d6ee7f18da6124c7da632e1a36d76217b825a8b",
    "f2": "35c66375081bf9f4924f365f2a5517dcfee3e3f4",
    "f3": "255490fe9047f26ea79cace0e80e0b2a50e9cbee",
    "f4": "79f39a5e7de73522f308aa2a1f5cd398b8af9d9c",
    "f5": "fdba52175f9426337604f794ef0a84f6327e7618",
    "f6": "a1e2fe96671621cd7e49bed74329a60bc22a6984",
}


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    coarse = _load(COARSE / "coarse_map_summary.json")
    refinement = _load(REFINE / "refinement_summary.json")
    cells = _load(REFINE / "refined_boundary_cells.json")["cells"]
    cert = _load(REFINE / "branch_extremal_certification.json")
    f4_jac = _load(FD / "local_jacobians.json")
    f4_policy = _load(FD / "step_policy.json")
    f5_sum = _load(F5 / "f5_summary.json")
    f5_stats = _load(F5 / "regime_statistics.json")["statistics"]
    f6_sum = _load(F6 / "f6_summary.json")
    f6_map = _load(F6 / "comparison_map.json")["points"]
    f6_trans = _load(F6 / "comparison_signature_transitions.json")

    # F6 metric sign classes from the corrected map.
    def _sign_class(proto, metric):
        vals = [r.get(proto, {}).get(metric) for r in f6_map
                if r.get(proto, {}).get(metric) is not None]
        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        return {"count": len(vals), "positive": pos, "negative": neg}

    # F5 regime sign classes.
    def _regime_sign(out, param):
        blocks = f5_stats["sanger"][param][out]
        return {
            regime: blocks[regime].get("sign", {})
            for regime in sorted(blocks)
        }

    # F3 extremal anchors (production + REF Phi).
    extremal_anchors = []
    for branch in sorted(cert):
        for side in ("N_side", "N1_side"):
            e = cert[branch].get(side)
            if e is None:
                continue
            ref_rows = e.get("reference_rows", [])
            extremal_anchors.append({
                "branch": branch, "side": side,
                "parameter": e["parameter"],
                "production_phi": round(e["production_phi"], 6),
                "reference_phi": {
                    r["solver"]: round(r["phi"], 6)
                    for r in ref_rows if r.get("phi") is not None},
                "reference_dual_stable": e["reference_dual_stable"],
            })

    snapshot = {
        "schema_version": "phase-f-gamma-k-sensitivity-regression-v1",
        "source_commit": {
            "f7a_prefreeze": "pre-freeze (F7A audit pending final tag)",
            **COMMITS,
        },
        "domain": {
            "gamma0_deg": [-9.0, -1.0], "gamma_step_deg": 0.25,
            "K": [1.0, 5.0], "K_step": 0.125,
            "canonical_centers": 1089,
        },
        "topology": {
            "qian_regime_counts": {"QIAN_RTI": 1089},
            "sanger_regime_counts": coarse["sanger"]["regime_counts"],
            "branch_count": 5,
            "branches": ["B0", "B1", "B2", "B3", "B4"],
            "boundary_cell_count": len(cells),
            "open_edges": refinement["open_boundaries"],
        },
        "grazing": {
            "phi_sign_consistency": "100%",
            "extremal_anchors": extremal_anchors,
            "recovered_canonical_count": 5,
            "recovered_verified": 5,
        },
        "fd": {
            "gamma_step_deg": f4_policy["gamma_step_deg"],
            "K_step": f4_policy["K_step"],
            "gamma_policy": f4_policy["gamma_policy"],
            "K_policy": f4_policy["K_policy"],
            "baseline_qian_jacobian": f4_jac["jacobians"]["baseline"]["qian"],
            "baseline_sanger_jacobian": (
                f4_jac["jacobians"]["baseline"]["sanger"]),
        },
        "f5": {
            "availability": f5_sum["availability"],
            "regime_sign_classes": {
                "dR_dgamma": _regime_sign("sanger_srti_range_m", "gamma"),
                "dR_dK": _regime_sign("sanger_srti_range_m", "K"),
                "qian_dR_dgamma": (
                    f5_stats["qian"]["gamma"]["qian_rti_range_m"]
                    ["whole-domain"]["sign"]),
            },
        },
        "f6": {
            "centers": len(f6_map),
            "protocol_b_valid": f6_sum["valid_paired"],
            "protocol_d": f6_sum["protocol_d"],
            "limiters": f6_sum["limiter_counts"],
            "checkpoint_modes": _load(F6 / "metric_statistics.json")[
                "checkpoint_modes"],
            "signature_count": f6_sum["signature_count"],
            "signature_transition_cells": f6_sum[
                "signature_transition_cells"],
            "signature_transition_by_reason": f6_sum[
                "signature_transition_by_reason"],
            "recovered_centers": f6_sum["recovered_centers"],
            "metric_sign_classes": {
                "delta_range_time": _sign_class("protocol_b",
                                                "delta_range_m"),
                "time_saving": _sign_class("protocol_c", "time_saving_s"),
                "delta_range_tau": _sign_class("protocol_d",
                                               "delta_range_m"),
            },
            "baseline_anchors": {
                "t_common_s": _load(F6 / "comparison_map.json")["points"][0][
                    "protocol_b"]["common_time_s"],
            },
        },
    }
    OUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"snapshot written: {OUT}")
    print(f"  schema = {snapshot['schema_version']}")
    print(f"  Sanger regimes = {snapshot['topology']['sanger_regime_counts']}")
    print(f"  cells = {snapshot['topology']['boundary_cell_count']}")
    print(f"  F6 D status = {snapshot['f6']['protocol_d']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
