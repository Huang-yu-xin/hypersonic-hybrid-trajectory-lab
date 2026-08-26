"""M3 -- preregistered direction decision policy (task Sec. 9-14).

Decision precedence (locked in configs/phase_m3/m3_scalar_gradient_v0.json,
bootstrap_locked.decision_precedence_locked):

    HOLD_INVALID    validity / legality failures    (highest precedence)
    HOLD_LOW_ESS    ESS_grad < 20
    WIDEN           g_ci_high < 0        (95% bootstrap percentile CI)
    SHRINK          g_ci_low  > 0
    HOLD_UNCERTAIN  CI contains 0        (lowest)

Point-sign alone is never a headline decision.
"""

from __future__ import annotations

from dataclasses import dataclass

WIDEN = "WIDEN"
SHRINK = "SHRINK"
HOLD_UNCERTAIN = "HOLD_UNCERTAIN"
HOLD_LOW_ESS = "HOLD_LOW_ESS"
HOLD_INVALID = "HOLD_INVALID"

DECISIONS = (WIDEN, SHRINK, HOLD_UNCERTAIN, HOLD_LOW_ESS, HOLD_INVALID)
ACTIVE_DECISIONS = (WIDEN, SHRINK)


@dataclass(frozen=True)
class DirectionRule:
    ess_min: float = 20.0

    def decide(self, *, validity_ok: bool, validity_reasons: tuple[str, ...] = (),
               ess_grad: float = float("nan"),
               g_ci_low: float = float("nan"),
               g_ci_high: float = float("nan")) -> str:
        """Precedence-locked WIDEN/SHRINK/HOLD rule."""
        if not validity_ok:
            return HOLD_INVALID
        if not (ess_grad >= self.ess_min):
            return HOLD_LOW_ESS
        if g_ci_high < 0.0:
            return WIDEN
        if g_ci_low > 0.0:
            return SHRINK
        return HOLD_UNCERTAIN


def evaluation_best_direction(m2_base: float, m2_widen: float,
                              m2_shrink: float,
                              rel_tol: float = 0.01) -> str:
    """Independent-evaluation best direction (task Sec. 14).

    WIDEN iff widen beats BOTH base and shrink; ties fall back to HOLD when no
    perturbation improves base by more than ``rel_tol`` relatively."""
    base = float(m2_base)
    w, s = float(m2_widen), float(m2_shrink)
    improves_w = w < base * (1.0 - rel_tol) and w < s
    improves_s = s < base * (1.0 - rel_tol) and s < w
    if improves_w and not improves_s:
        return WIDEN
    if improves_s and not improves_w:
        return SHRINK
    return "HOLD"


def step_sign_for(decision: str, delta_theta: float) -> float:
    """Preregistered action map: WIDEN->+dtheta, SHRINK->-dtheta, else 0."""
    if decision == WIDEN:
        return +float(delta_theta)
    if decision == SHRINK:
        return -float(delta_theta)
    return 0.0


def accuracy_among_active(records: list[dict]) -> dict:
    """Acc_dir and friends over ACTIVE (non-HOLD) trials only (task Sec. 24)."""
    active = [r for r in records
              if r["gradient"]["decision"] in ACTIVE_DECISIONS]
    if not active:
        return {"n_active": 0, "acc_dir": None}
    hits = sum(1 for r in active
               if r["gradient"]["decision"]
               == r["counterfactual"]["evaluation_best_direction"])
    return {
        "n_active": len(active),
        "n_correct": int(hits),
        "acc_dir": hits / len(active),
    }


__all__ = [
    "DirectionRule", "evaluation_best_direction", "step_sign_for",
    "accuracy_among_active", "DECISIONS", "ACTIVE_DECISIONS",
    "WIDEN", "SHRINK", "HOLD_UNCERTAIN", "HOLD_LOW_ESS", "HOLD_INVALID",
]
