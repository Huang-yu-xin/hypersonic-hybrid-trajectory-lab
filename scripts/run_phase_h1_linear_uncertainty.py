"""Phase-H1 fixed-topology linear uncertainty snapshot generator.

READ / COMPUTE / CROSS-CHECK / FREEZE only.

This script builds ``tests/data/phase_h1_linear_uncertainty_v1.json`` from
the ACCEPTED Phase-G frozen artifacts + the ACCEPTED H0 protocol.  It
performs NO physics beyond the first-order covariance algebra:

  * reads the H0 protocol (canonical-A scale, input family, alpha status);
  * reads the frozen G4 hybrid-STM snapshot and extracts the accepted
    ``phi_ref_01 / phi_ref_05 / phi_production`` fixed-time hybrid STMs for
    Qian T600, Sanger T600 and (descriptive) Sanger T900;
  * reads the frozen G5 predictability snapshot for the canonical-A
    ``sigma_max`` (fixed-time closure) and the accepted native-terminal
    ``eta / J`` + terminal reference values (terminal closure);
  * scales the maps with ``tilde Phi = S_A^-1 Phi S_A`` / ``tilde J_T =
    S_A^-1 J S_A`` / ``eta_scaled = eta S_A`` (H1 §10, §26);
  * builds the kernels ``K_x = tilde Phi R tilde Phi^T`` (canonical R = I)
    and ``K_T = tilde J_T R tilde J_T^T`` and every per-alpha response
    coefficient;
  * cross-checks the strong G5 identities (sqrt(lambda_max(K_x)) == G5
    sigma_max; principal direction vs G5 u1; terminal sigma_t/alpha == G5
    scaled_event_time_norm_seconds; terminal kernel max sigma == G5
    scaled_sigma_max; frozen-H0 numerical rank == G5 rank).

No Monte Carlo, no random draws, no gamma0-K scan, no new boundary
fitting, no optimization.  ``alpha`` stays symbolic: every scientific
quantity is reported as a PER-ALPHA RESPONSE COEFFICIENT.

Reproducible: running twice in a row on the same working tree must produce
a byte-identical output (no timestamps / no self-referential SHAs).

Run from the repository root:

    python scripts/run_phase_h1_linear_uncertainty.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hyptraj.uncertainty.protocol import (  # noqa: E402
    ALPHA_STATUS,
    CANONICAL_SCALE_KEY,
    STATE_ORDER_TUPLE,
    canonical_scale,
    canonical_scale_matrix,
)
from hyptraj.uncertainty.propagation import (  # noqa: E402
    compute_fixed_time_case,
    compute_terminal_case,
)

DATA = REPO / "tests" / "data"
G4 = json.loads((DATA / "phase_g4_hybrid_stm_v1.json").read_text(encoding="utf-8"))
G5 = json.loads((DATA / "phase_g5_predictability_metrics_v1.json").read_text(
    encoding="utf-8"))

OUT = DATA / "phase_h1_linear_uncertainty_v1.json"

SCHEMA_VERSION = "phase-h1-linear-uncertainty-v1"
STARTING_H0R_COMMIT = "4f9463f75cbf62b0a83312a67ea43fa173f77c12"
UPSTREAM_PHASE_G_COMMIT = "6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c"
UPSTREAM_PHASE_F_COMMIT = "96253f1ef7785764d8da3156d7d614d2b244b577"

FIXED_TIME_CASES = (
    ("qian_T600", "qian", "T600"),
    ("sanger_T600", "sanger", "T600"),
    ("sanger_T900", "sanger", "T900"),
)

UNIT_BY_STATE = {"r": "m", "theta": "rad", "v": "m/s", "gamma": "rad"}


def _as_list(a: np.ndarray) -> list:
    return np.asarray(a, dtype=float).round(10).tolist()


def _state_dict(arr: np.ndarray) -> dict:
    return {k: round(float(v), 10) for k, v in zip(STATE_ORDER_TUPLE, arr)}


def _closure_ok(err: float, tol: float = 1e-6) -> str:
    # descriptive algebraic-closure marker only; NOT an H2 acceptance
    # threshold (H1 §63 keeps the H2 acceptance criterion open).
    return "PASS" if (err == err and err < tol) else "CHECK"


def _fixed_time_payload(key: str, model: str, horizon_key: str) -> dict:
    ep = G4["endpoints"][key]
    g5ft = G5["fixed_time_canonical"][model][horizon_key]
    res = compute_fixed_time_case(
        model=model,
        horizon_s=float(ep["T"]),
        topology_signature=ep["topology_signature"],
        endpoint_mode=ep["endpoint_mode"],
        phi_ref_01=ep["phi_ref_01"],
        phi_ref_05=ep["phi_ref_05"],
        phi_production=ep["phi_production"],
        g5_sigma_max=g5ft["sigma_max"],
    )
    payload = {
        "model": res.model,
        "horizon_s": res.horizon_s,
        "topology_signature": list(res.topology_signature),
        "endpoint_mode": res.endpoint_mode,
        "phi_source": res.phi_source,
        "phi_ref_01": _as_list(np.asarray(ep["phi_ref_01"])),
        "phi_ref_05": _as_list(np.asarray(ep["phi_ref_05"])),
        "scaled_phi": _as_list(res.scaled_phi),
        "R": _as_list(res.R),
        "kernel_ref_01": _as_list(res.kernel_ref_01),
        "kernel_ref_05": _as_list(res.kernel_ref_05),
        "raw_eigenvalues": [round(float(x), 10) for x in res.spectrum.raw_eigenvalues],
        "eigenvalue_classification": list(res.spectrum.eigenvalue_classification),
        "rank": int(res.spectrum.numerical_rank),
        "nullity": int(res.spectrum.nullity),
        "sigma_rms_per_alpha": float(round(res.sigma_rms_per_alpha, 10)),
        "sigma_max_per_alpha": float(round(res.sigma_max_per_alpha, 10)),
        "principal_directions": _as_list(res.principal_directions),
        "physical_marginal_std_per_alpha": _state_dict(
            res.physical_marginal_std_per_alpha),
        "physical_marginal_units": dict(UNIT_BY_STATE),
        "G5_sigma_max": float(g5ft["sigma_max"]),
        "G5_sigma_crosscheck_error": float(round(res.g5_sigma_crosscheck_error, 12)),
        "G5_sigma_closure": _closure_ok(res.g5_sigma_crosscheck_error),
        "G5_u1_scaled_closure": float(round(
            abs(float(res.principal_directions[:, 0] @ np.asarray(
                g5ft["u1_scaled"], dtype=float))), 12)),
        "reference_kernel_error": {
            "max_abs_diff": float(round(res.reference_kernel_max_abs_diff, 12)),
            "material_rel_diff": float(
                round(res.reference_kernel_material_rel_diff, 12)),
            "sigma_max_diff": float(round(res.reference_sigma_max_diff, 12)),
            "sigma_rms_diff": float(round(res.reference_sigma_rms_diff, 12)),
            "principal_direction_alignment": float(
                round(res.reference_principal_direction_alignment, 12)),
            "rank_01": int(res.reference_rank_01),
            "rank_05": int(res.reference_rank_05),
        },
        "reference_stability_status": (
            "PASS" if res.reference_principal_direction_alignment > 1 - 1e-9
            and res.reference_rank_01 == res.reference_rank_05
            and res.reference_kernel_material_rel_diff < 1e-6 else "CHECK"),
        "production_kernel_error": {
            "max_abs_diff": float(round(res.production_kernel_max_abs_diff, 12)),
            "material_rel_diff": float(
                round(res.production_kernel_material_rel_diff, 12)),
            "sigma_max_diff": float(round(res.production_sigma_max_diff, 12)),
        },
    }
    if key == "sanger_T900":
        payload["descriptive_stress_case"] = True
        payload["fair_cross_model_comparison"] = False
    else:
        payload["descriptive_stress_case"] = False
        payload["fair_cross_model_comparison"] = True
    return payload


def _terminal_payload(model: str, key: str) -> dict:
    t = G5["terminal"][model]
    res = compute_terminal_case(
        model=model,
        terminal_kind=t["terminal_kind"],
        terminal_time=float(t["terminal_time"]),
        eta=t["eta"],
        J=t["J"],
        g5_eta_norm=float(t["scaled_event_time_norm_seconds"]),
        g5_scaled_sigma_max=float(t["scaled_sigma_max"]),
        g5_rank=int(t["rank"]),
        reference_status=t["reference_stability"]["status"],
    )
    return {
        "model": res.model,
        "terminal_kind": res.terminal_kind,
        "terminal_time": float(round(res.terminal_time, 6)),
        "R": _as_list(res.R),
        "eta": [round(float(x), 10) for x in res.eta],
        "eta_scaled": [round(float(x), 10) for x in res.eta_scaled],
        "J": _as_list(res.J),
        "J_scaled": _as_list(res.J_scaled),
        "terminal_state_kernel": _as_list(res.terminal_state_kernel),
        "raw_eigenvalues": [round(float(x), 10) for x in res.spectrum.raw_eigenvalues],
        "eigenvalue_classification": list(res.spectrum.eigenvalue_classification),
        "rank": int(res.spectrum.numerical_rank),
        "nullity": int(res.spectrum.nullity),
        "terminal_sigma_rms_per_alpha": float(
            round(res.terminal_sigma_rms_per_alpha, 10)),
        "terminal_sigma_max_per_alpha": float(
            round(res.terminal_sigma_max_per_alpha, 10)),
        "terminal_time_std_per_alpha": float(
            round(res.terminal_time_std_per_alpha, 10)),
        "scaled_state_time_cross_cov_per_alpha2": [
            round(float(x), 10) for x in res.scaled_state_time_cross_cov_per_alpha2
        ],
        "scaled_state_time_correlation": [
            None if np.isnan(x) else round(float(x), 10)
            for x in res.scaled_state_time_correlation
        ],
        "physical_marginal_std_per_alpha": _state_dict(
            res.physical_marginal_std_per_alpha),
        "physical_marginal_units": dict(UNIT_BY_STATE),
        "G5_eta_norm": float(t["scaled_event_time_norm_seconds"]),
        "G5_eta_crosscheck_error": float(round(res.g5_eta_crosscheck_error, 12)),
        "G5_eta_closure": _closure_ok(res.g5_eta_crosscheck_error),
        "G5_terminal_sigma_max": float(t["scaled_sigma_max"]),
        "G5_terminal_sigma_crosscheck_error": float(
            round(res.g5_terminal_sigma_crosscheck_error, 12)),
        "G5_terminal_sigma_closure": _closure_ok(
            res.g5_terminal_sigma_crosscheck_error),
        "G5_rank": int(res.g5_rank),
        "rank_matches_g5": bool(res.rank_matches_g5),
        "reference_status": res.reference_status,
    }


def build_snapshot() -> dict:
    fixed_time = {k: _fixed_time_payload(k, m, T) for k, m, T in FIXED_TIME_CASES}
    terminal = {
        "qian_RTI": _terminal_payload("qian", "qian"),
        "sanger_SRTI": _terminal_payload("sanger", "sanger"),
    }
    scales = canonical_scale()
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": "phase-h-uncertainty-risk-protocol-v1",
        "starting_h0r_commit": STARTING_H0R_COMMIT,
        "upstream_phase_g_commit": UPSTREAM_PHASE_G_COMMIT,
        "upstream_phase_f_commit": UPSTREAM_PHASE_F_COMMIT,
        "source_artifacts": {
            "phase_g4_hybrid_stm_v1.json": G4["schema_version"],
            "phase_g5_predictability_metrics_v1.json": G5["schema_version"],
            "consumption_rule": (
                "H1 consumes frozen Phase-G derivatives (G4 hybrid STM, "
                "G5 terminal eta/J); it does not redefine or repair them."
            ),
        },
        "state_order": list(STATE_ORDER_TUPLE),
        "canonical_scale": {
            "key": CANONICAL_SCALE_KEY,
            "status": "CANONICAL_SCALE_NUMERIC_VALUES_FROZEN",
            "values": {k: float(v) for k, v in scales.items()},
        },
        "input_family": (
            "Z0 = S_A^-1 delta X0 ~ N(0, alpha^2 R); canonical R = I "
            "=> tilde P0 = alpha^2 I (H0 §12, H1 §8)."
        ),
        "alpha_status": ALPHA_STATUS,
        "reporting_normalization": "PER_ALPHA_RESPONSE_COEFFICIENTS",
        "fixed_time": fixed_time,
        "terminal": terminal,
        "claim_boundaries": {
            "first_order_only": True,
            "fixed_topology_conditioned": True,
            "alpha_numeric_not_frozen": True,
            "monte_carlo_not_performed": True,
            "topology_probability_not_computed": True,
            "no_real_world_calibration": True,
            "native_terminal_not_fair_cross_model_ranking": True,
            "canonical_A_only_for_primary_result": True,
            "scaling_sensitivity_inherited": True,
            "interpretation": (
                "Under the frozen canonical-A isotropic dimensionless "
                "input covariance, linear models conditioned on the "
                "nominal frozen topology only.  NOT a nonlinear truth, NOT "
                "a topology-transition probability, NOT a real-world "
                "calibrated uncertainty, NOT yet nonlinear-MC validated "
                "for any finite alpha (H1 §37, §61, §64)."
            ),
        },
        "h2_handoff": {
            "linear_prediction_kernel": (
                "H2 will validate the linear prediction kernel / per-alpha "
                "coefficients against nonlinear Monte-Carlo "
                "(mean / covariance / principal spreads) and monitor the "
                "topology-preservation fraction (H1 §62)."
            ),
            "alpha_not_chosen_at_h1": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="write the H1 snapshot; default prints validation only")
    args = parser.parse_args()

    snapshot = build_snapshot()

    # self-validation: every frozen G5 closure must be PASS
    problems = []
    for key, case in snapshot["fixed_time"].items():
        if case["G5_sigma_closure"] != "PASS":
            problems.append(f"{key}: G5 sigma closure {case['G5_sigma_closure']}")
        if case["reference_stability_status"] != "PASS":
            problems.append(f"{key}: reference stability CHECK")
    for key, case in snapshot["terminal"].items():
        if case["G5_eta_closure"] != "PASS":
            problems.append(f"{key}: G5 eta closure {case['G5_eta_closure']}")
        if case["G5_terminal_sigma_closure"] != "PASS":
            problems.append(
                f"{key}: G5 terminal sigma closure {case['G5_terminal_sigma_closure']}")
        if not case["rank_matches_g5"]:
            problems.append(f"{key}: terminal rank mismatch with G5")

    if problems:
        for p in problems:
            print("  [CLOSURE] " + p)
        if not args.write:
            raise SystemExit("H1 closure check FAILED (see above).")

    if args.write:
        OUT.write_text(
            json.dumps(snapshot, indent=1, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        print(f"wrote {OUT.relative_to(REPO)}")
    else:
        print("closure check OK (no write; pass --write to emit the snapshot)")


if __name__ == "__main__":
    main()
