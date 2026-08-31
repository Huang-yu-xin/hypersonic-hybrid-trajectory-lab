"""M3-D reference characterization -- offline oracle machinery (task Sec. 7-9).

CRN batched evaluator replicating the FROZEN ``eval_proposal_is`` math
EXACTLY (w = exp(logp - logq) * 1_A ; M2 = mean(w^2) ; L_j = mean((w*1_j)^2))
but consuming the shared stream in B batches of n/b so that all three arms
of one state see the SAME (choice, standard_normal) sequence per batch --
identical component structure/order guarantees pairing, only the selected
component's Cholesky differs.  Paired contrasts therefore inherit batch-level
covariance cancellation exactly like the online counterfactual protocol.

Everything in this module is OFFLINE ORACLE data: it must never be imported
by any online code path (structural test test_m3d_no_oracle_leakage pins
this).
"""

from __future__ import annotations

import numpy as np

from hyptraj.event_semantics import TopologyLabel, event_indicator_from_topology

BATCHES_REF = 20            # locked: 20 sub-batches x 25k = N_ref per arm


def crn_batched_eval(arms: dict, bench_cfg, state_rng_key, n_ref: int,
                     n_batches: int = BATCHES_REF) -> dict:
    """Batched CRN evaluation for one state's three arms.

    ``arms`` maps arm name -> CovGaussianMixtureProposal sharing identical
    centers/weights/order; ``state_rng_key`` seeds ONE Generator reused in
    lock-step across arms within each batch.
    """
    n_b = int(n_ref) // int(n_batches)
    labels_all = {}
    out = {name: {"m2_batches": [], "p_batches": [],
                  "L_batches": {}} for name in arms}
    rng = np.random.default_rng(list(state_rng_key))

    for _ in range(n_batches):
        eps = None                                  # shared normal block
        comp = None                                 # shared choice vector
        w_by_arm = {}
        for name in ("base", "shrink", "widen"):    # fixed draw order
            prop = arms[name]
            if comp is None:
                comp = rng.choice(prop.n_components, size=n_b,
                                  p=prop.weights)
                eps = rng.standard_normal((n_b, prop.centers.shape[1]))
            chols = prop.chols
            z = prop.centers[comp] + np.einsum(
                "njk,nk->nj", np.stack([chols[c] for c in comp]), eps)
            logq = prop.log_density(z)
            lab = bench_cfg.label(z)
            ind = event_indicator_from_topology(lab).astype(float)
            logp = bench_cfg.logp(z)
            w = np.exp(logp - logq) * ind
            w_by_arm[name] = (w, lab)
        for name, (w, lab) in w_by_arm.items():
            modes = sorted(set(lab.tolist()) - {TopologyLabel.S0.value})
            out[name]["m2_batches"].append(float(np.mean(w ** 2)))
            out[name]["p_batches"].append(float(np.mean(w)))
            for mid in modes:
                out[name]["L_batches"].setdefault(
                    mid, []).append(float(np.mean((w * (lab == mid)) ** 2)))

    def summary(name):
        m2b = np.asarray(out[name]["m2_batches"])
        pb = np.asarray(out[name]["p_batches"])
        res = {
            "M2": float(m2b.mean()), "P": float(pb.mean()),
            "M2_batch_se": float(m2b.std(ddof=1) / np.sqrt(len(m2b))),
            "n_batches": int(n_batches), "batch_n": int(n_b),
            "m2_batches": [float(x) for x in out[name]["m2_batches"]],
            "L_modes": {}}
        for mid, vals in out[name]["L_batches"].items():
            v = np.asarray(vals)
            res["L_modes"][mid] = {"L": float(v.mean()),
                                   "se": float(v.std(ddof=1)
                                               / np.sqrt(len(v)))}
        return res

    return {name: summary(name) for name in arms}


def paired_contrast(a: dict, b: dict) -> tuple[float, float]:
    """(value, paired SE) of M2(a) - M2(b) from stored batch summaries."""
    m2a = np.asarray(a["m2_batches"], dtype=float)
    m2b = np.asarray(b["m2_batches"], dtype=float)
    d = m2a - m2b
    return float(d.mean()), float(d.std(ddof=1) / np.sqrt(d.size))


def batched_paired_se(m2_a: list[float], m2_b: list[float]) -> float:
    d = np.asarray(m2_a, dtype=float) - np.asarray(m2_b, dtype=float)
    return float(d.std(ddof=1) / np.sqrt(d.size))


def label_state(refs: dict, batches: dict, tau: float = 0.01,
                margin_min: float = 0.05,
                hold_window: float = 0.03, se_mult: float = 2.0) -> dict:
    """Frozen oracle-label rule (task Sec. 8-9) with support requirements.

    ``refs``  : arm name -> {M2, P, ...}
    ``batches``: arm name -> {m2_batches: [...], L_modes, ...}
    Returns oracle_action, direction margin, support flags.  Any required
    contrast failing |contrast| >= se_mult * SE_paired => REFERENCE_AMBIGUOUS.
    """
    b = refs["base"]["M2"]
    sh = refs["shrink"]["M2"]
    wi = refs["widen"]["M2"]

    se_sh = batched_paired_se(batches["base"]["m2_batches"],
                              batches["shrink"]["m2_batches"])
    se_wi = batched_paired_se(batches["base"]["m2_batches"],
                              batches["widen"]["m2_batches"])
    support = {
        "base_vs_shrink_supported": bool(abs(sh - b) >= se_mult * se_sh),
        "base_vs_widen_supported": bool(abs(wi - b) >= se_mult * se_wi),
    }

    r_sh = sh / b - 1.0
    r_wi = wi / b - 1.0
    widen_ok = (r_wi < -tau) and (wi < sh)
    shrink_ok = (r_sh < -tau) and (sh < wi)

    # LOCKED RULE: every contrast REQUIRED by the label decision must be
    # resolvable at >= se_mult x its batched paired SE.  A WIDEN label
    # requires both the base-vs-widen improvement contrast AND the
    # base-vs-shrink contrast (the ordering argument); SHRINK mirrored.
    if widen_ok:
        if not (support["base_vs_widen_supported"]
                and support["base_vs_shrink_supported"]):
            return {"oracle_action": "REFERENCE_AMBIGUOUS",
                    "direction_margin_Delta_dir":
                        float((sh - wi) / wi) if wi > 0 else float("inf"),
                    "support": support,
                    "ratios": {"shrink_over_base": float(r_sh),
                               "widen_over_base": float(r_wi)},
                    "ambiguity_reason": "unsupported_required_contrast"}
    if shrink_ok:
        if not (support["base_vs_shrink_supported"]
                and support["base_vs_widen_supported"]):
            return {"oracle_action": "REFERENCE_AMBIGUOUS",
                    "direction_margin_Delta_dir":
                        float((wi - sh) / sh) if sh > 0 else float("inf"),
                    "support": support,
                    "ratios": {"shrink_over_base": float(r_sh),
                               "widen_over_base": float(r_wi)},
                    "ambiguity_reason": "unsupported_required_contrast"}

    # direction margin operates over the TWO PERTURBATION ARMS ONLY
    # (locked operationalization in m3d_reference_characterization.json):
    #   best = labeled action, second-best = the OTHER perturbation
    if widen_ok and not shrink_ok:
        action, best, second = "WIDEN", wi, sh
    elif shrink_ok and not widen_ok:
        action, best, second = "SHRINK", sh, wi
    elif not widen_ok and not shrink_ok:
        # HOLD requires both perturbations inside the +-3% window
        inside = (abs(r_wi) <= hold_window) and (abs(r_sh) <= hold_window)
        action = "HOLD" if inside else "REFERENCE_AMBIGUOUS"
        best, second = b, min(wi, sh)
        support["hold_window_satisfied"] = bool(inside)
    else:
        action = "REFERENCE_AMBIGUOUS"      # both directions improve > tau:
        best, second = min(wi, sh), max(wi, sh)

    delta_dir = (second - best) / best if best > 0 else float("inf")

    result = {
        "oracle_action": action,
        "direction_margin_Delta_dir": float(delta_dir),
        "support": support,
        "ratios": {"shrink_over_base": float(r_sh),
                   "widen_over_base": float(r_wi)},
    }
    if action == "REFERENCE_AMBIGUOUS":
        return result
    if action == "HOLD":
        return result                       # class gate already checked
    if delta_dir < margin_min:
        result["oracle_action"] = "REFERENCE_AMBIGUOUS"
        result["margin_below_threshold"] = True
    return result
