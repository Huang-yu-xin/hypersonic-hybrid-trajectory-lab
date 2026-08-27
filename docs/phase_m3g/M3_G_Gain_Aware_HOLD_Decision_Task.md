# M3-G Gain-Aware HOLD Decision — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems
> **Method Track:** M3-G — Gain-Aware HOLD Decision (scalar, first version)
> **Status:** **PREREGISTERED — NOT STARTED**
> **Parent frozen tags:** `RareTopo-H3-v1.0`, `RareTopo-M1-v0`, `RareTopo-M1-D-v1.0`, `RareTopo-M2-v0`, `RareTopo-M3-v0`, `RareTopo-M3-D-v0`
> **Immediate predecessors:** M3-v0(direction estimation)、M3-D(sign-diverse benchmark; directional switching supported, adaptive advantage NOT established)
> **Date:** 2026-08-27 ｜ **M3-G scientific runs = 0**

---

# 0. FIRST ACTION — Build on the two frozen layers

Both freezes must be verified at every driver start:

```text
RareTopo-M3-v0   @ 32b285625494d9b3da08be3c559db3855df77667
RareTopo-M3-D-v0 @ 7bd58c5992615b8579b1814a3a3fcbea3cda9659
```

Confirmed frozen evidence carried forward:

- M3-D benchmark permanently sealed: 24 states, freeze v2 hash `b613f45dc6645c6d…`, oracle labels from corrected-label sidecar `m3d_labels_corrected_v2.json`;
- M3-D verdicts preserved verbatim: M3D-2 FAIL(HOLD recall 0.250), M3D-3 FAIL(R_fixed=0.988 vs cap 0.90), M3D-5 FAIL, Strong VRF=1.0304 PASS(**never** phrased as adaptive superiority);
- sanctioned failure-mechanism statement: `gradient-sign confidence != finite-step action-indifference` — WIDEN/SHRINK recalls both 1.00 while HOLD recall 0.250 shows the controller lacks an action-value gate.

No M3-G scientific experiment may run before THIS task document is committed.

---

# 1. Motivation and the Gap

The M3 controller family decides direction only:

```text
g < 0 -> WIDEN ; g > 0 -> SHRINK ; CI crosses 0 -> HOLD_UNCERTAIN
ESS_grad < 20 -> HOLD_LOW_ESS
```

The ORACLE, however, decides **action worth taking**:

```text
oracle HOLD = neither finite ±delta_theta step improves M2 by more than tau
              JUDGED AT THE REFERENCE BUDGET (action-indifference)
```

M3-D isolated the defect precisely: on oracle-HOLD states the sign was often confidently estimated yet the FIXED step's realized gain straddled the preregistered indifference window (per-seed medians r_w=-0.028, r_s=+0.052; 48/64 hold trials acted). Direction estimation and step-worthiness are DIFFERENT questions; the current policy answers only the first.

## The separation to be tested

```text
direction estimation   : keep VERBATIM (frozen M3 estimator + bootstrap + CI)
step-worthiness        : NEW pre-decision gate on the PREDICTED GAIN
```

---

# 2. Scientific Firewall

IMMUTABLE inputs:

```text
gradient formula / responsibility / ESS_grad=20 / fixed-stratified bootstrap
CI-sign rule & precedence                     (estimation layer untouched)
delta_theta_main = 0.20                       (all gain gates priced at it)
RareTopo-M3-D benchmark: the same 24 frozen states, same labels, same
reference files (m3d_candidate_pool*.json + m3d_labels_corrected_v2.json)
-- NO re-characterization, NO relabeling, NO state edits
seeds [2026..2033], pilot 20k/alpha .5, eval 100k/[seed,900001], CRN
legality checker / dual call accounting / tau=0.01 semantics of oracle
```

M3-G may NOT:

- modify or reinterpret the direction layer;
- touch any raw batch of earlier phases;
- relabel, add, delete, or re-characterize benchmark states;
- tune delta_theta or thresholds after seeing results;
- claim superiority beyond its preregistered gate set;
- enter full-matrix control.

Contribution of this phase is ONE decision-layer object evaluated against the sealed benchmark.

---

# 3. Primary Research Question

Does a preregistered **gain-aware HOLD rule** —

```text
act (WIDEN/SHRINK by frozen CI-sign) ONLY IF predicted finite-step gain >= floor
otherwise -> HOLD_GAIN      (new reason code, folded as HOLD with reason kept)
```

— recover oracle-HOLD behavior on the sealed sign-diverse benchmark WITHOUT destroying the perfect WIDEN/SHRINK performance, i.e., improve the action-value profile that made M3D-2 fail?

## Predicted-gain proxy (candidate object; final form locked in configs/phase_m3g BEFORE online)

First-order in theta = log s^2:

\[
\widehat{\Delta}_{rel} \;=\;
\frac{\widehat g_k\,\Delta\theta}{\widehat M_2}
\qquad(\Delta\theta=\pm0.20\text{ in the acted direction})
\]

with bootstrap CI for the gain propagated from the existing per-replicate estimates of $\hat g$ and $\hat M_2$ (same fixed-stratified replicates; no new pilot draws). Candidates to be compared head-to-head, one selected pre-online by the calibration protocol below and locked:

| variant | definition | note |
|---|---|---|
| GA1 | |\hat Δ_rel| ≥ ρ | pure magnitude |
| GA2 | upper CI bound of signed \hat Δ_rel still beyond −ρ / +ρ on the acted side | conservative, uses uncertainty like CI-sign does |

## Calibration protocol (pre-online, document-in-config, uses ONLY stored reference/layer_a data)

For ρ ∈ {0.0025, 0.005, 0.01, 0.02}: simulate the folded decisions on the STORED M3-D Layer A batch and pick the single global ρ maximizing accuracy subject to WIDEN/SHRINK recall ≥ 0.90 each; lock (variant, ρ); NOTHING is re-run on simulator data for selection.

## Preregistered floors/guards

- any acted state must remain legal under the frozen checker at the mapped arm (illegal → fold HOLD_INVALID exactly like M3-D audit discipline);
- oracle semantics unchanged: HOLD = action-indifference at reference budget with tau=0.01.

---

# 4. Benchmark & Protocol Reuse

Identical to M3-D D6 machinery, byte-for-byte:

- 24 sealed states × seeds [2026..2033] = 192 paired trials;
- pilot rng [seed,101]; arms CRN eval rng [seed,900001]; physical arms BASE/WIDEN/SHRINK only; all policies map onto them;
- baseline policy for ALL comparisons = the FROZEN M3-D controller (CI-sign, no gain gate), whose stored records ARE the baseline row-set — no rerun needed (bitwise replay equivalence must be asserted once as a test).

Gain-aware policy ADDS zero extra simulator calls: it filters the already-mapped GRADIENT actions using quantities computed inside the existing estimator pipeline.

---

# 5. Metrics

Core classification: Acc3, recalls per class, macro-F1, balanced accuracy, confusion matrix — reported ALWAYS alongside baseline deltas (Δ vs frozen-CI policy).

Action-value: median/global regret R_M2 tail statistics (P75/P95), plus R_fixed recomputed under the identical aggregate (median of per-state seed medians) against the same three fixed rules.

Diagnostic-only: distribution of |\hatΔ_rel| per class; fraction act-but-indifferent before/after gating; replay-control table inherited from M3-D D-F unchanged.

Statistical hierarchy identical to M3-D (NOT-IID; paired unit (state,seed)); paired bootstrap n=10,000 seed [20260827].

---

# 6. Gates

All thresholds fixed here; relaxation requires docs/phase_m3g/M3_G_PREREG_AMENDMENT_<date>.md BEFORE further runs.

```text
M3G-0 validity : both parent tags verified; task committed first; no benchmark
                 mutation (freeze sha matches b613f45d...); no-oracle-leakage
                 structural tests green; full python -m pytest -q pass.
M3G-1 baseline-parity : replayed baseline row-set bitwise equals the frozen
                 M3-D layer_a records (guards accidental drift).
M3G-2 non-regression : Acc3_gain >= 0.75 AND WIDEN recall >= 0.90 AND
                 SHRINK recall >= 0.90 (i.e., the gate must not pay for its
                 HOLD gains by breaking perfect classes).
M3G-3 hold-recovery : HOLD recall >= 0.50 (from 0.250) AND act-but-indifferent
                 count strictly decreases (>= -30% relative).
M3G-4 value-direction : R_fixed(GA) <= R_fixed(baseline CI-sign) on the same
                 aggregate -- the gate must move the controller TOWARD the
                 best-fixed rule, not away. Exploratory tier reports the gap
                 to the absolute 0.90 line without claiming it.
M3G-5 near-oracle retained : median R_M2 <= 0.05.
Strong (budget VRF > 1 under deployable accounting): reported separately;
                 PASSING IT CONFERS NO SUPERIORITY CLAIM (M3-D lesson).
```

Interpretation branch map (Sec.41 style):

```text
A  gate works: M3G-2..5 all PASS           -> gain-aware value SUPPORTED (scalar)
B  hold-recovers but classes degrade       -> threshold needs class conditioning;
                                              future prereg only
C  nothing recovers                         -> action-value must come from a
                                              different signal (curvature etc.);
                                              scalar policy closed as-is
D  gates pass but R_fixed still >> 0.90     -> report honestly; adaptive
                                              advantage over AW remains unproven
```

---

# 7. Required Tests (minimum)

```text
test_m3g_baseline_bitwise_parity          # Sec.6 replay guard
test_m3g_gain_proxy_formula               # Delta_rel == g*dtheta/M2 exact
test_m3g_gate_variant_ga1_ga2             # folding rules incl reason codes
test_m3g_calibration_freeze_consistency   # chosen rho reproducible from config
test_m3g_no_new_simulator_calls           # runtime assertions zero extra draws
test_m3g_non_regression_metrics           # Sec.5 metric plumbing
test_m3g_result_schema                    # raretopo-m3g-v0 record shape
test_m3g_illegal_arm_fold                 # legality discipline inherits M3-D audit
```

Run full `python -m pytest -q` before any gate audit.

---

# 8. Outputs Layout

```text
docs/phase_m3g/
├── M3_G_Gain_Aware_HOLD_Decision_Task.md    (this file)
├── M3_G_Methodology.md
├── M3_G_Validity_Audit.md
└── M3_D_Final_Report-style Final Report

configs/phase_m3g/
├── m3g_gain_gate_v0.json                    (variant+rho locked BEFORE online)
└── m3g_protocol.json                        (protocol constants copied+frozen)

src/hyptraj/m3g/{gain_gate.py, metrics.py}
scripts/run_m3g_calibration.py               (offline only)
scripts/run_m3g_online.py                    (replay + gate evaluation)
results/phase_m3g/{calibration/,layer_a_replay/,summary/}
figures/phase_m3g/
```

---

# 9. Claim Boundary (draft locks, finalized after results)

If M3G-2..5 PASS:

> **On the sealed sign-diverse M3-D benchmark, a preregistered gain-aware HOLD layer recovers action-indifference behavior without sacrificing direction performance, reducing spurious finite-step actions while keeping the estimator untouched.**

If B/C/D branches: record negative/mechanistic finding verbatim in the report; never phrase Strong VRF>1 as adaptive superiority.

Forbidden always: universal optimality, full-matrix claims, cross-benchmark transfer, "gradient proven" wording, threshold post-hoc tuning narratives.

---

# 10. Execution Order

```text
Step 0  verify RareTopo-M3-v0 & RareTopo-M3-D-v0 tags -> STOP otherwise
G0      commit this task + m3g_protocol.json            (zero science)
G1      write src/hyptraj/m3g + tests; full pytest green
G2      offline calibration from stored batches -> lock variant/rho in config
G3      commit calibration lock                          (still zero sims)
G4      online replay-evaluation of the gated policy over the sealed benchmark
G5      gate audit M3G-0..5 + Strong -> summary json
G6      Methodology / Validity Audit / Final Report + figures
```

---

# 11. One-Line State

```text
H3=M1=M1D=M2=M3v0=M3Dv0 all frozen
M3-G = preregistered, scientific runs = 0
next = commit task, then build the gain-gate modules offline
```
