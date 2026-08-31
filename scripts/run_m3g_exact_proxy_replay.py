"""M3-G exact-proxy calibration replay (freeze-audit, handoff-corrected
prompt Sec. 4-5).

Rebuilds the FULL 8-candidate calibration table using the ORIGINAL
preregistered proxies (task doc 9720456 Sec. 3):

    GA1 : act iff |g_hat*dtheta|/M2_hat_pilot >= rho
    GA2 : act iff the UPPER end of the PER-REPLICATE signed-gain CI
          (bootstrap_gain_replicates: g_r*dtheta/M2_r replicates) <= -rho

The pilot draws and the frozen fixed-stratified bootstrap are REPLAYED
deterministically per (state, seed) (rng [seed,101] and [seed,424243]);
NO arm evaluation is performed, NO new sealed-evaluation row is produced:
    extra simulator scientific calls = 0
    (by the accounting definition of the prompt: pure audit replay of
    already-performed deterministic draws, identical samples to the
    sealed batch -- additionally asserted via 192/192 g_hat bitwise
    parity against the stored Layer-A records).

Output: results/phase_m3g/summary/exact_proxy_calibration_replay.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.event_semantics import event_indicator_from_topology
from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3.covariance_gradient import MixtureSpec, component_responsibility
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    variance_mass_importance,
)
from hyptraj.m3d.adaptation import draw_online_pilot
from hyptraj.m3d.benchmark_states import assemble_state
from hyptraj.m3d.metrics import three_class_metrics
from hyptraj.m3g.gain_proxy import DELTA_THETA_MAIN, bootstrap_gain_replicates
from hyptraj.m3g.metrics import arm_legal_at, select_candidate

REPO = Path(__file__).resolve().parents[1]
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))
STORED = json.loads((REPO / "results" / "phase_m3d" / "layer_a"
                     / "m3d_layer_a_v1.json").read_text(encoding="utf-8"))
SEALED = json.loads((REPO / "results" / "phase_m3g" / "layer_a"
                     / "m3g_online_v1.json").read_text(encoding="utf-8"))
DEST = REPO / "results" / "phase_m3g" / "summary" \
    / "exact_proxy_calibration_replay.json"

RHO_GRID = [0.0025, 0.005, 0.01, 0.02]
SEEDS = list(range(2026, 2034))


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _quantile_upper(vals, level: float = 0.975) -> float | None:
    good = np.asarray(vals)
    good = good[np.isfinite(good)]
    if good.size < 2:
        return None
    return float(np.quantile(good, level))


def main() -> int:
    bench_cache = {r["config_id"]: r for r in load_freeze()[
        "benchmark_configs"]}
    stored = {(r["state_id"], int(r["seed"])): r for r in STORED["records"]}
    sealed = {(r["state_id"], int(r["seed"])): r for r in
              SEALED["gated_records"]}

    cells = []          # per-cell exact-proxy quantities
    parity_bad = 0
    for s_rec in FREEZE_DOC["states"]:
        cid = s_rec["config_id"]
        bc = config_from_record(bench_cache[cid])
        st = assemble_state(bc, float(s_rec["s2"]))
        assert not isinstance(st, dict)
        prop = st.proposal()
        k = st.component_index
        spec = MixtureSpec(np.asarray(prop.weights, float),
                           np.asarray(prop.centers, float),
                           tuple(np.asarray(c, float) for c in prop.covs))
        for seed in SEEDS:
            key = (s_rec["state_id"], int(seed))
            z, logp, logr, strata = draw_online_pilot(st, seed, 20_000, 0.5)
            labels = st.bench_cfg.label(z)
            ind = event_indicator_from_topology(labels).astype(float)
            a = variance_mass_importance(
                z, np.asarray(prop.weights, float),
                np.asarray(prop.centers, float), list(prop.covs), logp,
                logr, ind)
            resp = component_responsibility(spec, z, k)
            sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                           z - prop.centers[k][None, :])
            est = scalar_gradient_estimate(a, resp, sq, s2=st.s2,
                                           dim=st.dim)
            raw = str(stored[key]["gradient"]["action"])
            # replay parity: the replayed frozen outputs must equal the
            # stored Layer-A record bitwise (guards audit-replay integrity)
            if float(est["g_hat"]) != float(
                    stored[key]["gradient"]["g_hat"]):
                parity_bad += 1
            if not est["valid_pointwise"]:
                continue
            br = bootstrap_gain_replicates(
                a, resp, sq, strata, s2=st.s2, dim=st.dim,
                dtheta=+DELTA_THETA_MAIN,  # arrays are direction-free;
                bootstrap_seed_key=(seed, 424243))  # signs derived below
            g_r = np.asarray(br["g_replicates"])
            m2_r = np.asarray(br["M2_replicates"])
            m2_pilot = float(est["M2_hat"])
            cells.append({
                "state_id": s_rec["state_id"], "seed": int(seed),
                "oracle": str(stored[key]["oracle_action"]),
                "raw": raw,
                "g_hat": float(est["g_hat"]),
                "m2_hat_pilot": m2_pilot,
                "g_r": g_r, "m2_r": m2_r,
            })
    assert parity_bad == 0, f"replay parity failed on {parity_bad} cells"
    n = len(cells)
    assert n == 192

    def decision(cell, variant, rho):
        raw = cell["raw"]
        if raw not in ("WIDEN", "SHRINK"):
            return "HOLD", raw
        dtheta = +DELTA_THETA_MAIN if raw == "WIDEN" else -DELTA_THETA_MAIN
        if not arm_legal_at(_s2_of(cell), dtheta):
            return "HOLD", "HOLD_INVALID"
        if variant == "GA1":
            mag = abs(cell["g_hat"] * dtheta) / cell["m2_hat_pilot"]
            act = bool(mag >= rho)
        else:  # GA2 exact: per-replicate signed-gain CI upper end
            signed_r = cell["g_r"] * dtheta / cell["m2_r"]
            upper = _quantile_upper(signed_r)
            if upper is None:
                act = False
            else:
                act = bool(upper <= -rho)
        return (raw if act else "HOLD"), ("EXECUTED" if act else "HOLD_GAIN")

    table = {}
    for variant in ("GA1", "GA2"):
        for rho in RHO_GRID:
            finals = [decision(c, variant, rho)[0] for c in cells]
            y = [c["oracle"] for c in cells]
            m = three_class_metrics(y, finals)
            key = f"{variant}-{rho}"
            table[key] = {
                "variant": variant, "rho": float(rho),
                "accuracy": m["accuracy"],
                "balanced_accuracy": m["balanced_accuracy"],
                "macro_F1": m["macro_F1"],
                "recall_per_class": m["recall_per_class"],
                "final_action_counts": {k: finals.count(k)
                                        for k in ("WIDEN", "SHRINK",
                                                  "HOLD")},
            }
    # baseline row uses the sealed M3-D deployed actions
    y_true = [c["oracle"] for c in cells]
    y_base = [stored[(c["state_id"], c["seed"])]["validity"]
              ["deployed_action"] for c in cells]
    mb = three_class_metrics(y_true, y_base)
    table["baseline_M3-D"] = {
        "variant": "M3-D", "rho": None, "accuracy": mb["accuracy"],
        "balanced_accuracy": mb["balanced_accuracy"],
        "macro_F1": mb["macro_F1"],
        "recall_per_class": mb["recall_per_class"], "final_action_counts":
            {k: y_base.count(k) for k in ("WIDEN", "SHRINK", "HOLD")},
    }

    sel = select_candidate(table)

    # per-trial action divergence under the SELECTED policy (GA2-0.0025)
    sel_key = sel["selected"]["key"] if sel["selected"] else "GA2-0.0025"
    divergences = 0
    div_rows = []
    for c in cells:
        exp = decision(c, "GA2", 0.0025)[0]
        se = str(sealed[(c["state_id"], c["seed"])]["gain"]["final_action"])
        if exp != se:
            divergences += 1
            div_rows.append({"state_id": c["state_id"], "seed": c["seed"],
                             "exact": exp, "sealed": se})

    payload = {
        "schema_version": "raretopo-m3g-exact-proxy-calibration-replay-v0",
        "stage": "freeze_audit_replay",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "unit_note": "exact-proxy calibration replay over the SAME frozen "
                     "(state, seed) units as the sealed evaluation; pure "
                     "audit replay of deterministic pilot+bootstrap draws",
        "extra_simulator_scientific_calls": 0,
        "replay_parity_g_hat_mismatches": parity_bad,
        "n_trials": n,
        "proxy_definitions": {
            "GA1": "act iff |g_hat*dtheta|/M2_hat_pilot >= rho "
                   "(prereg-intended pilot M2_hat denominator)",
            "GA2": "act iff upper end of PER-REPLICATE signed-gain CI "
                   "(g_r*dtheta/M2_r replicates, frozen fixed-stratified) "
                   "<= -rho",
        },
        "table": table,
        "selection": sel,
        "frozen_selection": {"key": "GA2-0.0025", "variant": "GA2",
                             "rho": 0.0025},
        "selection_matches_frozen": bool(
            sel["selected"] and sel["selected"] ==
            {"key": "GA2-0.0025", "variant": "GA2", "rho": 0.0025}),
        "closed_policy_divergence_from_sealed": {
            "policy": "GA2-0.0025",
            "trials_compared": n,
            "action_divergence_count": divergences,
            "rows": div_rows,
        },
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[saved] {DEST.relative_to(REPO)}")
    print("selection:", sel["selected"],
          "| matches frozen:", payload["selection_matches_frozen"],
          "| divergence:", divergences)
    return 0


def _s2_of(cell) -> float:
    """Look up the state's frozen s2 for the legality check."""
    for s_rec in FREEZE_DOC["states"]:
        if s_rec["state_id"] == cell["state_id"]:
            return float(s_rec["s2"])
    raise KeyError(cell["state_id"])


if __name__ == "__main__":
    raise SystemExit(main())
