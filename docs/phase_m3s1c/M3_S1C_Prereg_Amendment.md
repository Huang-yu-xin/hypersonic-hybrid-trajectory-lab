# M3-S1C Prereg Amendment Record

Date: 2026-09-06.  Nature: **preregistration semantics amendment only** —
no scientific design change, zero scientific simulator calls, zero trials
started, `EXECUTION_AUTHORIZED` remains **NO**.

This amendment formalizes two interpretations that the initial M3-S1C
preregistration (commit `3bd967d`) already implemented implicitly, per the
amendment taskbook (`M3_S1C_Prereg_Amendment_and_Remote_Push_Taskbook_2026-09-06.md`):

## AMENDMENT A — config-diversity round rule (frozen)

The W stratum of the 42-state protected reserve offers 10 states across only
5 unique configs, so an 8-state W stratum cannot be built under a
max-2-states-per-config cap.  The formal rule (now verbatim in
`configs/phase_m3s1c/m3s1c_panel.json -> selection_rule` and implemented in
`scripts/run_m3s1c.py::pick_rounds` / `::select_panel`):

1. group eligible untouched states by `config_id`;
2. within each config, sort by the frozen
   `selection_rank = SHA256("M3-S1C-PANEL-V1|" + config_id + "|" + state_id)`;
3. config-diversity rounds: round k takes at most the k-th ranked state from
   each config; candidates within a round are ordered only by their own
   frozen rank; stop exactly at 8 per stratum;
4. no S1/gradient/V1/controller result, theory descriptor, development
   outcome or manual preference may affect selection.

Scientific meaning: **lexicographically maximize physical-config diversity
before allowing additional repeated states from an already represented
config.**  The implementation's canonical rank string is exactly the
taskbook string (no deviation; verified by test `test_rank_string_matches_frozen_definition`).

## AMENDMENT B — truth-vs-comparator exposure semantics (frozen)

`previous_confirmation_exposure` (bit 8) is defined as previous
**controller/comparator/policy-level** confirmation exposure — never
filename-based.  Classification is by record content with nearest-ancestor
namespace inheritance (implemented in `scripts/run_m3s1c.py`
`COMPARATOR_FIELDS` / `TRUTH_FIELDS` / `classify_ns` / `walk_records` /
`record_class` / `scan_confirm_artifacts`):

- **comparator** (FORBIDDEN): any comparator/policy field on a
  candidate-bearing record — g_hat, g_ci_low, g_ci_high, ci_low, ci_high,
  gradient_valid, S1, s1_score, V1, v1_score, r_hat, se_r_hat,
  selected_action, controller_action, deployment, deploy, abstain,
  policy_decision, action_sign, ESS_grad — or a comparator-pattern
  namespace (`GRAD|PROBE|TRIAL|V1|S1|POLICY`).
- **truth_reference** (ALLOWED): truth/reference fields — confirmed_label,
  provisional_label, P_ref_hash, p_ref_hash — or a truth-stream namespace
  (`...-REF` / `...-CONFIRM`) with no comparator field on the record.  This
  is the frozen high-budget truth stratum the confirmation panel requires;
  without the distinction the confirmation design is self-contradictory
  (frozen truth is a prerequisite, not an exposure).
- **unknown** => **UNRESOLVED => STOP panel freeze**; unknown artifacts are
  never auto-allowed (amendment Sec. 3.6).  At this freeze:
  unresolved candidate-bearing records = **0**.

## Invariance gate (amendment Sec. 5/6) — ALL PASS

| item | value |
|---|---|
| panel state-set identical | YES (24 states) |
| panel order identical | YES (stratum order + state_id) |
| panel csv sha256 (old == new) | `1b1e390f3c87e3e8556f37a92b6e4e4988a6b738d62eb7c6ab9eb7e39d3921a5` |
| seeds identical (192 values) | YES (canonical content sha256 `6e81dbb3265114d9…`) |
| W / S / ND unique configs | 5 / 7 / 8 |
| S1 formula unchanged | YES (`abs(g_hat) / ((ci_high-ci_low)/(2*1.959963984540054))`) |
| threshold unchanged | `5.4417199447782` |
| sign mapping unchanged | `g_hat < 0 => WIDEN; g_hat > 0 => SHRINK` |
| gates unchanged | coverage >= 0.75, wrong <= 0.05, ND unsafe <= 0.20 |
| budget unchanged | 24 states x 8 replicates x 20,000 = 3.84M; V1 probe = 0 |
| pre-amendment baseline snapshot | `results/phase_m3s1c/preflight/_pre_amendment_baseline.json` |

The panel JSON file hash itself changed only because the frozen
`selection_rule` text was added to it; the scientific panel identity
(`m3s1c_panel.csv` sha256, carried as `panel_hash` in every future trial
record) is unchanged.

## Hash-lock regeneration (amendment Sec. 8)

`results/phase_m3s1c/preflight/m3s1c_prereg_hashes.json` regenerated after
the amendment (14 files: parent/reserve/exposure/panel/seed/preflight audit
JSONs + 7 config contracts).  Git-tracking status (repo `.gitignore`
excludes `results/`):

- **git-tracked** (durable, remote-auditable): `configs/phase_m3s1c/*.json`
  (7 contracts incl. panel + seeds), `docs/phase_m3s1c/*.md` (this record,
  preregistration, audits, approval), `scripts/run_m3s1c.py`,
  `tests/test_m3s1c_prereg.py`.
- **results-only (untracked, local)**: `m3s1c_prereg_hashes.json`,
  `m3s1c_panel.csv`, exposure bitsets, path preflight rows, pre-amendment
  baseline snapshot.  The committed Preregistration doc carries the key
  hash anchors (panel csv sha256, seeds manifest sha256, S1 contract
  sha256); the untracked manifest is re-derivable and re-verifiable from
  the tracked artifacts.

## Tests (amendment Sec. 7)

- S1C suite: 42 passed / 0 failed (31 original + 11 amendment-specific:
  round-rule semantics incl. the 5-configs/8-needed case, rank-string
  freeze, order independence, controller-signal blindness, committed-panel
  equivalence; truth/comparator/unknown classification, filename
  irrelevance, live 42-candidate clean audit).
- Full regression: **2198 passed / 0 failed, 3 warnings, 812.87s**
  (python -m pytest -q, exit 0).
