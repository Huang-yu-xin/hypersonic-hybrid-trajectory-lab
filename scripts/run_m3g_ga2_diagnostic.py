"""M3-G post-hoc diagnostic (labelled, non-scientific): quantify the GA2
operationalisation -- linear propagation of the frozen g-CI vs the TRUE
per-replicate CI of Delta_rel (bootstrap_gain_replicates) -- on the sealed
24x8 cells.  Replays ONLY the pilot draw + frozen bootstrap (no arm
evaluations, no changes to any record); the locked gate decisions remain
those of the sealed online batch.

Output: results/phase_m3g/summary/m3g_ga2_propagation_diagnostic.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.adaptation import draw_online_pilot
from hyptraj.m3d.benchmark_states import assemble_state
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    variance_mass_importance,
)
from hyptraj.m3.covariance_gradient import MixtureSpec, component_responsibility
from hyptraj.m3g.gain_proxy import (
    DELTA_THETA_MAIN,
    bootstrap_gain_replicates,
    ga2_upper_end,
)

REPO = Path(__file__).resolve().parents[1]
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))
DEST = REPO / "results" / "phase_m3g" / "summary" \
    / "m3g_ga2_propagation_diagnostic.json"

SEEDS = list(range(2026, 2034))


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    bench_cache = {r["config_id"]: r for r in load_freeze()[
        "benchmark_configs"]}
    rho = 0.0025
    rows, disagree = [], 0
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
            z, logp, logr, strata = draw_online_pilot(st, seed, 20_000, 0.5)
            labels = st.bench_cfg.label(z)
            ind = (labels != "NOMINAL").astype(float)
            a = variance_mass_importance(
                z, np.asarray(prop.weights, float),
                np.asarray(prop.centers, float),
                list(prop.covs), logp, logr, ind)
            resp = component_responsibility(spec, z, k)
            sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                           z - prop.centers[k][None, :])
            est = scalar_gradient_estimate(a, resp, sq, s2=st.s2,
                                           dim=st.dim)
            if not est["valid_pointwise"]:
                continue
            delr = bootstrap_gain_replicates(
                a, resp, sq, strata, s2=st.s2, dim=st.dim,
                dtheta=+DELTA_THETA_MAIN,
                bootstrap_seed_key=(seed, 424243))
            g_ci_low, g_ci_high = delr["g_ci_low"], delr["g_ci_high"]
            m2_pilot = float(est["M2_hat"])
            # decision A (locked linear form, pilot-M2 normaliser):
            upper_linear = ga2_upper_end(g_ci_low, g_ci_high,
                                         +DELTA_THETA_MAIN, m2_pilot)
            dec_linear = (upper_linear <= -rho)
            # decision B (true per-replicate upper end):
            upper_rep = float(delr["delta_rel_signed_ci_high"])
            dec_rep = (upper_rep <= -rho)
            rows.append({
                "state_id": s_rec["state_id"], "seed": int(seed),
                "g_hat": float(est["g_hat"]),
                "g_ci_low": g_ci_low, "g_ci_high": g_ci_high,
                "upper_linear": upper_linear,
                "upper_per_replicate": upper_rep,
                "n_valid_reps": int(delr["n_bootstrap_valid"]),
                "decide_linear": bool(dec_linear),
                "decide_per_replicate": bool(dec_rep)})
            if dec_linear != dec_rep:
                disagree += 1
    payload = {
        "schema_version": "raretopo-m3g-ga2-propagation-diagnostic-v0",
        "stage": "post_hoc_diagnostic_non_scientific",
        "git_commit": _git(),
        "rho_checked": rho,
        "dtheta": +DELTA_THETA_MAIN,
        "trials": len(rows),
        "linear_vs_per_replicate_disagreements": disagree,
        "deep_rows": rows,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[saved] {DEST.relative_to(REPO)} -- {len(rows)} trials, "
          f"disagreements={disagree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())