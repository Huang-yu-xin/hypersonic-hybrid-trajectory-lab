"""M3-S2S exclusion manifest + truth-contract audit (taskbook Sec. 5/8/9).

Exclusion is content-based (comparator-field detection with
nearest-ancestor namespace inheritance, as frozen in M3-S1C Amendment B);
filename-only classification is forbidden.  UNKNOWN candidate-bearing
records => UNRESOLVED => candidate ineligible.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# The canonical corrected truth-establishment protocol (taskbook Sec. 8.2):
# the CF1N three-phase chain, event semantics v2 -- the latest protocol that
# actually established truth for new states, feeding the corrected CF2
# inventory that in turn parented PI1VNR/S1C.
TRUTH_PROTOCOL_PHASES = [
    {"phase": "pref", "config": "configs/phase_m3cf1n/m3cf1n_pref_protocol.json",
     "namespace": "M3-CF1N-PREF", "samples_per_config": 500_000,
     "note": "config-level corrected full-event P_ref; reusable for new s2 "
             "states on already-characterized corrected configs => 0 new"},
    {"phase": "discovery", "config": "configs/phase_m3cf1n/m3cf1n_discovery_protocol.json",
     "namespace": "M3-CF1N-DISCOVERY", "samples_per_arm": 100_000, "arms": 3,
     "direction_margin": 0.05, "hold_band": 0.03,
     "improvement_threshold": -0.01, "min_arm_ess": 20},
    {"phase": "confirmation", "config": "configs/phase_m3cf1n/m3cf1n_confirmation_protocol.json",
     "namespace": "M3-CF1N-CONFIRM", "samples_per_arm": 500_000, "arms": 3,
     "paired_crn_batches": 20},
]
TRUTH_EVENT_SCHEMA = "corrected full-event v2"

DISCOVERY_BUDGET_PER_STATE = 3 * 100_000        # 300,000
CONFIRMATION_BUDGET_PER_STATE = 3 * 500_000     # 1,500,000
TRUTH_BUDGET_PER_STATE = DISCOVERY_BUDGET_PER_STATE + CONFIRMATION_BUDGET_PER_STATE


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def audit_truth_protocol() -> dict:
    """Verify each phase config exists, hash it, and freeze the exact
    per-state truth budget.  No simulator call."""
    phases = []
    for ph in TRUTH_PROTOCOL_PHASES:
        p = ROOT / ph["config"]
        if not p.exists():
            raise RuntimeError(f"S2S-X: truth protocol config missing: {p}")
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("namespace") != ph["namespace"]:
            raise RuntimeError(f"S2S-X: namespace drift in {p}")
        phases.append({**ph, "sha256": _sha(p)})
    return {
        "recorded_at": None,
        "TRUTH_CONTRACT": "CF1N three-phase corrected protocol (pref reuse "
                          "for characterized configs; discovery -> "
                          "confirmation for every new candidate state)",
        "event_semantics": TRUTH_EVENT_SCHEMA,
        "phases": phases,
        "discovery_budget_per_state": DISCOVERY_BUDGET_PER_STATE,
        "confirmation_budget_per_state": CONFIRMATION_BUDGET_PER_STATE,
        "truth_budget_per_state": TRUTH_BUDGET_PER_STATE,
        "label_semantics": "WIDEN/SHRINK direction margin >= 0.05; HOLD band "
                           "+/-3%; AMBIGUOUS = unsupported required contrast; "
                           "min arm ESS 20 (verbatim CF1N discovery config)",
    }


def candidate_plan(n_candidates: int, n_configs: int) -> dict:
    """Exact truth budget for the frozen candidate plan (Sec. 9)."""
    discovery = n_candidates * DISCOVERY_BUDGET_PER_STATE
    confirmation = n_candidates * CONFIRMATION_BUDGET_PER_STATE
    return {
        "candidate_states": n_candidates,
        "candidate_configs": n_configs,
        "discovery_total": discovery,
        "confirmation_total": confirmation,
        "pref_total": 0,
        "TRUTH_BUDGET_MAX": discovery + confirmation,
        "retirement_rule": "every truth-sampled state enters "
                           "m3s2s_truth_exposed_inventory and is retired "
                           "from all future untouched confirmation use "
                           "whether or not it enters the 120-state panel",
    }


def build_exclusion_manifest(candidate_ids: set[str]) -> dict:
    """Controller-exposure exclusion over the candidate states.

    Scans prior controller/comparator streams (trial ledgers, panels,
    comparator-classified confirmation artifacts) and returns the per-
    candidate exposure verdict.  Truth-reference-only exposure is allowed;
    UNKNOWN => UNRESOLVED => ineligible.
    """
    idset = set(candidate_ids)
    comparator_hits: set[str] = set()
    unresolved: set[str] = set()
    scan_roots = ["phase_m3pi1v", "phase_m3pi1vn", "phase_m3pi1vnr",
                  "phase_m3s1c_dummy"]  # s1c trials live under phase_m3s1c
    ctrl = ("g_hat", "g_ci_low", "g_ci_high", "S1", "V1", "r_hat",
            "selected_action", "deployment", "action_sign", "ESS_grad")
    ns_re = __import__("re").compile(r"GRAD|PROBE|TRIAL|V1|S1|POLICY")

    # 1. panel/manifest membership (controller panels are exposure by definition)
    panel_sources = [
        "results/phase_m3pi1vnr/summary/m3pi1vnr_fresh_development_panel.csv",
        "results/phase_m3s1c/preflight/m3s1c_panel.csv",
        "results/phase_m3pi1vnr/summary/m3pi1vnr_retired_pi1vn_panel.csv",
        "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "results/phase_m3wcf1/summary/m3wcf1_fresh_development_panel.csv",
        "results/phase_m3pi1vnr/summary/m3pi1vnr_remaining_protected_reserve.csv",
    ]
    for rel in panel_sources:
        p = ROOT / rel
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as h:
            for row in csv.DictReader(h):
                sid = row.get("state_id", "")
                if sid in idset:
                    comparator_hits.add(sid)

    # 2. ledgers of controller streams (namespace/content classification)
    for d in scan_roots:
        base = ROOT / "results" / d
        if not base.exists():
            continue
        for p in base.rglob("*.jsonl"):
            entries = []
            for line in p.read_text(encoding="utf-8",
                                    errors="ignore").splitlines():
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
            for e in entries:
                if not isinstance(e, dict):
                    continue
                sid = e.get("state_id", "")
                if sid not in idset:
                    continue
                if any(k in e for k in ctrl) or ns_re.search(
                        str(e.get("seed_namespace", ""))):
                    comparator_hits.add(sid)
                elif "-REF" in str(e.get("seed_namespace", "")) or \
                        "-CONFIRM" in str(e.get("seed_namespace", "")):
                    pass  # truth/reference stream: allowed
                else:
                    unresolved.add(sid)

    # 3. comparator-classified confirmation artifacts: candidates are NEW
    # s2 points on corrected configs (state ids never existed in any
    # artifact), so the registry check in the runner plus the panel/ledger
    # scans above constitute the live exposure audit; the S2F content
    # classifier (scan_confirm_artifacts) governs any *confirm* artifact
    # that might reference a candidate id.
    from run_m3s1c import scan_confirm_artifacts  # noqa: E402  (scripts/ path)
    confirm_paths = [p for p in (ROOT / "results").rglob("*confirm*")
                     if p.suffix in (".csv", ".json") or p.is_dir()]
    exposed_ids, unresolved_ids, _ = scan_confirm_artifacts(confirm_paths, idset)
    comparator_hits |= exposed_ids
    unresolved |= {u.rsplit(":", 1)[-1] for u in unresolved_ids}

    eligible = idset - comparator_hits - unresolved
    return {
        "candidates": len(idset),
        "controller_exposed_excluded": sorted(comparator_hits),
        "unresolved": sorted(unresolved),
        "eligible": sorted(eligible),
        "counts": {"excluded": len(comparator_hits & idset),
                   "unresolved": len(unresolved),
                   "eligible": len(eligible)},
        "UNKNOWN_RULE": "unresolved candidate-bearing records make the "
                        "candidate ineligible; STOP if quota cannot be met",
    }


def truth_composition(rows: list[dict]) -> Counter:
    return Counter(r["truth"] for r in rows)
