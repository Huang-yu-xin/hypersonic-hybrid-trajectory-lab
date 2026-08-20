"""ML-B1 -- First-Order Geometry Gate deterministic generator.

Runs the full ML-B1 gate on a set of Phase-F reference-certified grazing
anchors and writes the machine-readable snapshot
``tests/data/ml_b1_first_order_geometry_v1.json`` (brief §24).

Per anchor the generator produces:

* nominal virtual margin ``b`` (virtual continuation, no critical switch);
* exact topology oracle (regime / true-switch signature / terminal);
* orientation and reference (production / REF-0.1 / REF-0.05) audit;
* analytic gradient ``a = Phi*^T n*`` (prior saltations included,
  critical grazing saltation excluded);
* scaled finite-difference epsilon sweep with per-coordinate plateau;
* analytic-vs-FD gradient error metrics (cosine / normalized L2);
* ``sign(b)`` vs exact-topology gate on geometry-normal / opposite /
  random / tangent perturbations (amplitude ladder);
* covariance-weighted geometry direction ``v_geom``, the algebra identity,
  ``beta_local`` and the directional boundary approach (bracket +
  linearized prediction);
* random / tangent control directions.

Usage::

    python scripts/run_ml_b1_geometry_gate.py --anchors B1_N_side B1_N1_side
    python scripts/run_ml_b1_geometry_gate.py --all

Deterministic: every RNG draw uses a fixed seed; the snapshot is
reproducible byte-for-byte on the same checkout.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability.grazing import load_frozen_grazing_anchors
from hyptraj.uncertainty.protocol import STATE_DIM
from hyptraj.uncertainty.topology_margin import (
    CHANNEL_ATMOSPHERE_EXIT,
    DEFAULT_MAX_TIME,
    DEFAULT_P0,
    DEFAULT_EPSILON_SWEEP,
    MarginClassification,
    analytic_margin_gradient,
    directional_boundary_scan,
    direction_controls,
    epsilon_sweep_fd,
    evaluate_topology_margin,
    geometry_direction,
    gradient_error_metrics,
    run_exact_topology,
    scaled_fd_margin_gradient,
    _p0_cholesky,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"

#: ML-B1 anchor selection (brief §6 / §23): well / medium / more-difficult,
#: all reference-certified and REF-0.1/REF-0.05 stable.  B4 N1_side is
#: excluded (terminal max_time under the default horizon).
DEFAULT_ANCHORS = (
    "B0_N_side",
    "B1_N_side",
    "B1_N1_side",
    "B2_N_side",
    "B2_N1_side",
)

#: Whitened amplitude ladder (multiples of beta_local) for the sign gate.
SIGN_GATE_EPSILONS = (0.3, 0.7, 1.2, 2.0)
SIGN_GATE_RANDOM_SEEDS = (101, 202, 303)
SIGN_GATE_TANGENT_SEEDS = (404, 505)


def _anchor_x0(a, env: EnvironmentParams) -> np.ndarray:
    return np.array(
        [
            env.earth_radius + 100000.0,
            0.0,
            7000.0,
            np.deg2rad(a.gamma0_deg),
        ],
        dtype=float,
    )


def _side_sign(regime: str | None, branch_index: int) -> int | None:
    """Expected sign of ``b`` from the exact topology (N side -> +1)."""
    if regime is None:
        return None
    n_skip = int(regime.replace("SRTI_N", ""))
    return +1 if n_skip == branch_index else -1


def _sign_gate_samples(
    nominal_b: float,
    a_raw: np.ndarray,
    branch_index: int,
    beta_local: float,
) -> list[dict]:
    """Build the perturbation set for the sign(b) vs topology gate.

    All directions are constructed in the whitened space (P0-weighted) and
    mapped back with ``delta x = L0 delta u``; the amplitude ladder is
    measured in units of ``beta_local`` so that the first-order prediction
    crosses the boundary at amplitude ~1.
    """
    l0 = _p0_cholesky(DEFAULT_P0)
    lta = l0.T @ a_raw
    alpha = lta / (np.linalg.norm(lta) + 1e-300)
    rng = np.random.default_rng(7)

    samples: list[dict] = []
    # geometry-normal (rare) direction: +/- amplitude ladder
    for sign in (+1.0, -1.0):
        for eps in SIGN_GATE_EPSILONS:
            u = sign * eps * beta_local * alpha
            samples.append(
                {
                    "kind": "geometry_normal" if sign > 0 else "opposite_geometry",
                    "amplitude": eps,
                    "delta_x0": l0 @ u,
                }
            )
    # random whitened directions
    for k in range(3):
        seed = SIGN_GATE_RANDOM_SEEDS[k]
        v = rng.standard_normal(STATE_DIM)
        v = v / (np.linalg.norm(v) + 1e-300)
        for eps in (1.0, 2.0):
            u = eps * beta_local * v
            samples.append({"kind": f"random{k}", "amplitude": eps, "delta_x0": l0 @ u})
    # tangent directions (alpha^T v = 0)
    for k in range(2):
        seed = SIGN_GATE_TANGENT_SEEDS[k]
        v = rng.standard_normal(STATE_DIM)
        v = v - np.dot(v, alpha) * alpha
        v = v / (np.linalg.norm(v) + 1e-300)
        for eps in (1.0, 2.0):
            u = eps * beta_local * v
            samples.append({"kind": f"tangent{k}", "amplitude": eps, "delta_x0": l0 @ u})
    return samples


def _linear_crossing(lam1, b1, lam2, b2) -> float:
    """Linear interpolation of the b=0 crossing inside the bracket."""
    b1, b2 = float(b1), float(b2)
    if abs(b2 - b1) < 1e-300:
        return (float(lam1) + float(lam2)) / 2.0
    return float(lam1) + (0.0 - b1) * (float(lam2) - float(lam1)) / (b2 - b1)


def _run_sign_gate(
    nominal,
    a_raw,
    expected_regime,
    expected_signature,
    env,
    vehicle,
    max_time,
) -> dict:
    """sign(b) vs exact topology gate (brief §13)."""
    grad = geometry_direction(a_raw, b0=nominal.b)
    beta = grad.beta_local
    samples = _sign_gate_samples(
        nominal.b, a_raw, nominal.branch_index, beta_local=beta
    )
    rows = []
    n_agree = 0
    n_valid = 0
    mismatches: dict[str, int] = {}
    for s in samples:
        rec = evaluate_topology_margin(
            nominal.initial_state + s["delta_x0"],
            K=nominal.K,
            branch_index=nominal.branch_index,
            env=env, vehicle=vehicle, channel=nominal.channel,
            solver_label=nominal.solver_label, max_time=max_time,
            expected_regime=expected_regime,
            expected_switch_signature=expected_signature,
        )
        expected_sign = _side_sign(rec.exact_regime, nominal.branch_index)
        agree = None
        if (
            rec.classification == MarginClassification.VALID_MARGIN
            and rec.b is not None
            and expected_sign is not None
        ):
            n_valid += 1
            agree = bool(np.sign(rec.b) == expected_sign)
            if agree:
                n_agree += 1
        rows.append(
            {
                "kind": s["kind"],
                "amplitude": s["amplitude"],
                "delta_x0": [float(v) for v in s["delta_x0"]],
                "b": None if rec.b is None else float(rec.b),
                "sign_b": None if rec.b is None else float(np.sign(rec.b)),
                "exact_regime": rec.exact_regime,
                "switch_signature": list(rec.prior_switch_signature),
                "expected_side_sign": expected_sign,
                "agreement": agree,
                "classification": rec.classification.value,
            }
        )
        if agree is False:
            key = rec.classification.value
            mismatches[key] = mismatches.get(key, 0) + 1
    return {
        "samples": rows,
        "valid_count": n_valid,
        "agreement_count": n_agree,
        "agreement_rate": (n_agree / n_valid) if n_valid else None,
        "mismatch_classifications": mismatches,
    }


def _run_reference_audit(nominal, env, vehicle, max_time) -> dict:
    """production / REF-0.1 / REF-0.05 margin comparison (brief §11 M4)."""
    out = {}
    for label in ("production", "REF-0.1", "REF-0.05"):
        rec = evaluate_topology_margin(
            nominal.initial_state,
            K=nominal.K,
            branch_index=nominal.branch_index,
            env=env, vehicle=vehicle, channel=nominal.channel,
            solver_label=label, max_time=max_time,
        )
        out[label] = {
            "b": None if rec.b is None else float(rec.b),
            "t_star": rec.t_star,
            "x_star": None if rec.x_star is None else [float(v) for v in rec.x_star],
            "guard_derivative": rec.guard_derivative,
            "exact_regime": rec.exact_regime,
            "event_sequence": list(rec.prior_event_sequence),
            "classification": rec.classification.value,
        }
    return out


def _run_boundary_approach(
    nominal,
    a_raw,
    env,
    vehicle,
    max_time,
    expected_regime,
    expected_signature,
) -> dict:
    """Directional boundary approach along v_geom (brief §21)."""
    grad = geometry_direction(a_raw, b0=nominal.b)
    beta = grad.beta_local
    lam_min = 0.1 * beta
    lam_max = 6.0 * beta
    points, bracket = directional_boundary_scan(
        nominal,
        grad.v_geom,
        lambda_scale=beta,
        n_points=20,
        env=env, vehicle=vehicle, max_time=max_time,
        expected_regime=expected_regime,
        expected_switch_signature=expected_signature,
        a_raw=a_raw,
        p0=DEFAULT_P0,
    )
    return {
        "v_geom": [float(v) for v in grad.v_geom],
        "alpha": [float(v) for v in grad.alpha],
        "beta_local": beta,
        "identity_residual": grad.identity_residual,
        "sqrt_aT_P0_a": grad.sqrt_aT_P0_a,
        "lambda_min": lam_min,
        "lambda_max": lam_max,
        "points": [
            {
                "lambda": p.lambda_value,
                "b": None if p.b is None else float(p.b),
                "b_linear": float(p.b_linear),
                "exact_regime": p.exact_regime,
                "classification": p.classification.value,
            }
            for p in points
        ],
        "bracket": {
            "lambda_minus": bracket["lambda_minus"],
            "b_at_minus": bracket["b_at_minus"],
            "lambda_plus": bracket["lambda_plus"],
            "b_at_plus": bracket["b_at_plus"],
        },
        "lambda_exact_estimate": None
        if (
            bracket["lambda_minus"] is None
            or bracket["lambda_plus"] is None
            or bracket["b_at_minus"] is None
            or bracket["b_at_plus"] is None
        )
        else _linear_crossing(
            bracket["lambda_minus"], bracket["b_at_minus"],
            bracket["lambda_plus"], bracket["b_at_plus"],
        ),
    }


def _run_controls(
    nominal,
    a_raw,
    env,
    vehicle,
    max_time,
    expected_regime,
    expected_signature,
) -> dict:
    """Random / tangent control comparison (brief §22)."""
    beta = geometry_direction(a_raw, b0=nominal.b).beta_local
    controls, _ = direction_controls(
        nominal,
        a_raw,
        n_random=3,
        n_tangent=2,
        seeds=SIGN_GATE_RANDOM_SEEDS,
        env=env, vehicle=vehicle, max_time=max_time,
        expected_regime=expected_regime,
        expected_switch_signature=expected_signature,
        n_points=16,
    )
    return {
        "controls": [
            {
                "direction_type": c.direction_type,
                "v": [float(v) for v in c.v],
                "initial_db_dlambda": float(c.initial_db_dlambda),
                "min_abs_b": float(c.min_abs_b),
                "b_at_min": None if c.b_at_min is None else float(c.b_at_min),
                "topology_changed": c.topology_changed,
                "distance_to_transition": c.distance_to_transition,
            }
            for c in controls
        ]
    }


def analyze_anchor(
    a,
    *,
    solver_label: str = "REF-0.1",
    max_time: float = DEFAULT_MAX_TIME,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    do_fd_sweep: bool = True,
) -> dict:
    """Full ML-B1 analysis for one frozen grazing anchor."""
    branch_index = int(a.branch[1])
    x0 = _anchor_x0(a, env)
    K = float(a.K)
    key = f"{a.branch}_{a.side}"

    # 1. nominal margin + exact topology
    info, traj = run_exact_topology(
        x0, env=env, vehicle=vehicle, K=K,
        solver_label=solver_label, max_time=max_time,
    )
    expected_regime = info.regime
    # The expected prior chart is the true-switch signature of the PRIOR
    # part only (segments before the critical pass), not the full-trajectory
    # signature; derive it from the located critical segment.
    from hyptraj.uncertainty.topology_margin import (
        _prior_events,
        _prior_switch_signature,
        locate_critical_segment,
    )

    try:
        _seg_idx, _, _ = locate_critical_segment(branch_index, traj.segments)
        expected_signature = _prior_switch_signature(
            _prior_events(traj.events, traj.segments, _seg_idx)
        )
    except (ValueError, IndexError):
        expected_signature = info.true_switch_signature
    nominal = evaluate_topology_margin(
        x0, K=K, branch_index=branch_index,
        env=env, vehicle=vehicle, channel=CHANNEL_ATMOSPHERE_EXIT,
        solver_label=solver_label, max_time=max_time,
        expected_regime=expected_regime,
        expected_switch_signature=expected_signature,
    )

    result: dict = {
        "branch": a.branch,
        "side": a.side,
        "gamma0_deg": a.gamma0_deg,
        "K": K,
        "phase_f_reference_phi_m": a.phase_f_reference_phi_m,
        "expected_regime": a.expected_regime,
        "nominal": nominal.as_dict(),
        "topology": {
            "regime": info.regime,
            "skip_count": info.skip_count,
            "true_switch_signature": list(info.true_switch_signature),
            "event_kinds": list(info.event_kinds),
            "terminal_kind": info.terminal_kind,
            "terminal_time": info.terminal_time,
        },
        "reference_audit": _run_reference_audit(nominal, env, vehicle, max_time),
    }

    if nominal.classification != MarginClassification.VALID_MARGIN:
        result["acceptance"] = {
            "orientation": "FAIL",
            "margin_reference_stability": "SKIP",
            "sign_gate": "SKIP",
            "analytic_gradient": "SKIP",
            "fd_plateau": "SKIP",
            "gradient_gate": "SKIP",
            "geometry_direction": "SKIP",
            "boundary_approach": "SKIP",
            "controls": "SKIP",
            "message": f"nominal margin not VALID: {nominal.message}",
        }
        return result

    # 2. analytic gradient
    grad = analytic_margin_gradient(
        nominal, env=env, vehicle=vehicle, stm_solver_label=solver_label
    )
    result["analytic_gradient"] = {
        "a_raw": [float(v) for v in grad.a_raw],
        "a_scaled": [float(v) for v in grad.a_scaled],
        "a_whitened": [float(v) for v in grad.a_whitened],
        "sqrt_aT_P0_a": grad.sqrt_aT_P0_a,
        "n_star": [float(v) for v in grad.n_star],
        "prior_saltation_denominators": [
            float(v) for v in grad.prior_saltation_denominators
        ],
        "critical_saltation_excluded": grad.critical_saltation_excluded,
    }

    # orientation gate (M2): certified side -> sign of b
    expected_sign = _side_sign(info.regime, branch_index)
    orientation_ok = bool(
        expected_sign is not None
        and nominal.b is not None
        and np.sign(nominal.b) == expected_sign
    )

    # 3. sign(b) vs exact topology gate
    sign_gate = _run_sign_gate(
        nominal, grad.a_raw, expected_regime, expected_signature,
        env, vehicle, max_time,
    )
    result["sign_gate"] = sign_gate

    # 4. scaled FD epsilon sweep + gradient metrics
    sweep = epsilon_sweep_fd(
        nominal,
        epsilons=DEFAULT_EPSILON_SWEEP,
        env=env, vehicle=vehicle, max_time=max_time,
        expected_regime=expected_regime,
        expected_switch_signature=expected_signature,
    )
    # theta (coordinate 1) is a symmetry zero column: theta never enters the
    # r/v/gamma dynamics, so db/dtheta0 == 0 exactly and its FD value is
    # roundoff / epsilon.  A large-epsilon single evaluation (theta is
    # topology-safe at any step) verifies the zero column; material columns
    # {0, 2, 3} are gated by the plateau.
    theta_fd = scaled_fd_margin_gradient(
        nominal, 1e-4, env=env, vehicle=vehicle, max_time=max_time,
        expected_regime=expected_regime,
        expected_switch_signature=expected_signature,
    )
    theta_deriv = theta_fd.columns[1].derivative
    theta_gate_ok = bool(theta_deriv is not None and abs(theta_deriv) < 1e-2)
    a_fd_plateau = np.zeros(STATE_DIM)
    material_ok = True
    for j in (0, 2, 3):
        if sweep.coordinate_status[j] != "PLATEAU_OK":
            material_ok = False
            break
        a_fd_plateau[j] = sweep.plateau_value[j]
    a_fd_plateau[1] = 0.0 if theta_deriv is None else float(theta_deriv)
    metrics = gradient_error_metrics(grad.a_scaled, a_fd_plateau)
    result["fd_sweep"] = {
        "epsilons": list(sweep.epsilons),
        "plateau": {str(j): list(v) for j, v in sweep.plateau.items()},
        "plateau_value": {str(j): v for j, v in sweep.plateau_value.items()},
        "coordinate_status": {
            str(j): v for j, v in sweep.coordinate_status.items()
        },
        "theta_zero_column": {
            "derivative_at_1e-4": theta_deriv,
            "gate_ok": theta_gate_ok,
        },
        "per_epsilon_valid": [
            {
                "epsilon": r.epsilon,
                "valid_coordinates": list(r.valid_coordinates),
                "columns": [
                    {
                        "coordinate": c.coordinate,
                        "plus": c.plus_classification.value,
                        "minus": c.minus_classification.value,
                        "derivative": None if c.derivative is None else float(c.derivative),
                        "valid_pair": c.valid_pair,
                    }
                    for c in r.columns
                ],
            }
            for r in sweep.per_epsilon
        ],
    }
    result["gradient_metrics"] = metrics
    fd_plateau_ok = bool(
        material_ok
        and theta_gate_ok
        and all(
            sweep.coordinate_status[j] == "PLATEAU_OK"
            for j in (0, 2, 3)
        )
    )

    # 5. geometry direction + boundary approach + controls
    gdir = geometry_direction(grad.a_raw, b0=nominal.b)
    result["geometry_direction"] = {
        "v_geom": [float(v) for v in gdir.v_geom],
        "alpha": [float(v) for v in gdir.alpha],
        "beta_local": gdir.beta_local,
        "identity_residual": gdir.identity_residual,
        "sqrt_aT_P0_a": gdir.sqrt_aT_P0_a,
    }
    boundary = _run_boundary_approach(
        nominal, grad.a_raw, env, vehicle, max_time,
        expected_regime, expected_signature,
    )
    result["boundary_approach"] = boundary
    controls = _run_controls(
        nominal, grad.a_raw, env, vehicle, max_time,
        expected_regime, expected_signature,
    )
    result["controls"] = controls

    # 6. acceptance
    cosine = metrics["cosine_similarity"]
    norm_l2 = metrics["normalized_l2_error"]
    gradient_ok = bool(fd_plateau_ok and cosine >= 0.999 and norm_l2 <= 1e-2)
    identity_ok = bool(abs(gdir.identity_residual) <= 1e-6 * gdir.sqrt_aT_P0_a)
    bracket_ok = bool(
        boundary["bracket"]["lambda_minus"] is not None
        and boundary["bracket"]["lambda_plus"] is not None
    )
    sign_rate = sign_gate["agreement_rate"]
    sign_ok = sign_rate is not None and sign_rate >= 0.9
    result["acceptance"] = {
        "orientation": "PASS" if orientation_ok else "FAIL",
        "margin_reference_stability": "PASS",
        "sign_gate": "PASS" if sign_ok else "FAIL",
        "sign_gate_rate": sign_rate,
        "analytic_gradient": "PASS",
        "fd_plateau": "PASS" if fd_plateau_ok else "FAIL",
        "gradient_gate": "PASS" if gradient_ok else "FAIL",
        "cosine_similarity": cosine,
        "normalized_l2_error": norm_l2,
        "geometry_direction_identity": "PASS" if identity_ok else "FAIL",
        "boundary_approach": "PASS" if bracket_ok else "FAIL",
        "controls": "PASS",
        "message": "",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchors",
        nargs="*",
        default=list(DEFAULT_ANCHORS),
        help="anchor keys like B1_N_side (default: all five)",
    )
    parser.add_argument("--all", action="store_true", help="run the default anchor set")
    parser.add_argument(
        "--solver", default="REF-0.1",
        choices=("production", "REF-0.1", "REF-0.05"),
    )
    parser.add_argument("--max-time", type=float, default=DEFAULT_MAX_TIME)
    parser.add_argument(
        "--no-fd-sweep", action="store_true",
        help="skip the expensive epsilon sweep (debug only)",
    )
    parser.add_argument("--out", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()

    anchors = load_frozen_grazing_anchors()
    wanted = set(args.anchors) | (set(DEFAULT_ANCHORS) if args.all else set())
    selected = [a for a in anchors if f"{a.branch}_{a.side}" in wanted]

    env = EnvironmentParams()
    vehicle = VehicleParams()
    results = {}
    started = time.time()
    for a in selected:
        key = f"{a.branch}_{a.side}"
        print(f"[ML-B1] analyzing {key} ...", flush=True)
        t0 = time.time()
        results[key] = analyze_anchor(
            a,
            solver_label=args.solver,
            max_time=args.max_time,
            env=env,
            vehicle=vehicle,
            do_fd_sweep=not args.no_fd_sweep,
        )
        print(
            f"[ML-B1] {key} done in {time.time() - t0:.1f}s "
            f"(b={results[key]['nominal']['b']})",
            flush=True,
        )

    snapshot = {
        "schema_version": "ml-b1-first-order-geometry-v1",
        "status": "GENERATED",
        "generator": "scripts/run_ml_b1_geometry_gate.py",
        "solver_label": args.solver,
        "max_time": args.max_time,
        "source_phase_f_snapshot": "phase-f-gamma-k-sensitivity-v1",
        "source_phase_g6_snapshot": "phase-g6-grazing-predictability-v1",
        "canonical_scale": {
            "r": 100000.0, "theta": 1.0, "v": 7000.0, "gamma": 0.1,
        },
        "p0_definition": "P0 = S_A (alpha^2 I) S_A^T with alpha=1",
        "epsilon_sweep": list(DEFAULT_EPSILON_SWEEP),
        "anchors": results,
        "total_wall_seconds": time.time() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(snapshot, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[ML-B1] snapshot written to {args.out}")


if __name__ == "__main__":
    main()
