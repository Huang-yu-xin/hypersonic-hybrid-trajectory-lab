# M3-CA Cost-Efficiency Attribution — Preregistered Task Lock

> Stage: M3-CA  
> Parent freeze: `RareTopo-M3-BV2-v0` at `912ed9771c34c50cc05825c7a5f3590553b5dfb0`  
> Analysis type: artifact-only accounting audit  
> Scientific runs authorized: **zero**

## 1. Question and primary endpoint

M3-BV2 reports that M3-G-v1 captures approximately 97.1% of the Oracle
adaptive headroom within the frozen scalar proposal family, while its median
budget-adjusted VRF is approximately 0.0084. M3-CA asks whether this gap is
primarily attributable to the proposal/benchmark regime, adaptation overhead,
an accounting inconsistency, or a mixed bottleneck.

The primary diagnostic is fixed before analysis:

\[
VRF_{\mathrm{budget}}^{\mathrm{freeOracle}} > 1\;?
\]

## 2. Scientific firewall

The following invariant is binding:

```text
extra_simulator_calls = 0
```

M3-CA must not generate pilots or final evaluations and must not introduce new
seeds, benchmark states, controller variants, rho values, proposals, budgets,
or M3-Q work. Analysis code is limited to reading frozen artifacts, arithmetic
reconstruction, descriptive summaries, tables, figures, hashing, and tests.

If a requested quantity is absent from the frozen sources, it is reported as:

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
```

No simulation may be used to fill the gap.

## 3. Locked sources

The source manifest must cover, at minimum:

- `results/phase_m3bv2/controller_evaluation.json`
- `results/phase_m3bv2/value_analysis.json`
- `results/phase_m3bv2/decision_analysis.json`
- `results/phase_m3bv2/reuse_record.json`
- `results/phase_m3bv/reference/m3bv_candidate_pool.json`
- `results/phase_m3bv/reference/m3bv_headline_stability.json`
- the BV2 Decision and Value freeze JSON files and configs
- the frozen M3-D and M3-G-v1 protocol/configuration records
- the M1-D benchmark freeze containing stored event probabilities

Every source receives a SHA-256 hash before analysis and is rechecked after
analysis. Sources are read-only and may not be modified by M3-CA.

## 4. Cost semantics

Deployable cost is

\[
C_{\mathrm{deploy}}
=C_{\mathrm{pilot}}+C_{\mathrm{decision}}+C_{\mathrm{selected}}.
\]

The frozen controller record accounts for `pilot_n = 20,000`,
`eval_n = 100,000`, and a total deployable budget of 120,000 calls. Decision
logic has no separately recorded simulator calls and therefore contributes
zero simulator-call cost; its CPU/wall-clock cost is not identifiable from the
frozen artifacts.

Reference characterization, benchmark construction, counterfactual arms,
Oracle discovery, all-fixed comparisons, diagnostics, report generation, and
figures are audit-only and excluded from deployable VRF.

BestFixed and FreeOracle pay no pilot or decision cost and pay only 100,000
selected-arm evaluation calls. FreeAdaptation keeps the recorded M3-G-v1
action and evaluation unchanged while setting pilot and decision costs to zero.

For a stored arm result,

\[
VRF_{\mathrm{proposal}}
=\frac{p(1-p)/N_{eval}}{(M_2-\hat p^2)/N_{eval}},
\qquad
VRF_{\mathrm{budget}}
=\frac{p(1-p)/B}{(M_2-\hat p^2)/N_{eval}}.
\]

When replicate-level `P_hat` was not stored for a frozen comparison arm, the
analysis uses the corresponding existing 500k reference-arm `P` and labels
that convention in the ledger; it must not silently invent or regenerate a
replicate estimate.

## 5. Headline reproduction gate

Before attribution, independently recompute the unified objective

\[
J(\pi)=\operatorname{median}_{state}\left[
\operatorname{median}_{rep}\log\frac{M_2(\pi)}{M_2(BASE)}\right]
\]

and verify:

- BestFixed is ALWAYS_WIDEN;
- `G_Oracle` is approximately 0.054152;
- `G_v1` is approximately 0.052560;
- capture is approximately 97.1%;
- median recorded M3-G-v1 `VRF_budget` is approximately 0.0084;
- M3-D and M3-G-v1 Value-Axis actions are identical.

Failure of any headline item stops scientific attribution and produces Verdict
C. No counterfactual conclusions are permitted after such a failure.

## 6. Locked analyses

After the reproduction gate passes:

1. Reconstruct a method/state cost ledger separating deployable and audit-only
   calls.
2. Compute BestFixed, FreeAdaptation, and FreeOracle counterfactual VRFs.
3. Build the log-efficiency ladder CrudeMC -> BestFixed -> FreeOracle ->
   M3-G-v1 without claiming exact causal additivity.
4. Retain all 24 Value-Axis states and the frozen 12 WIDEN / 12 SHRINK split.
5. Report class-conditional results, state-level losses, and pilot fractions.
6. Compute descriptive Spearman associations only for fields already present.
   Association is not interpreted as causation.

## 7. Verdict gate

- **A — Proposal/regime bottleneck:** FreeOracle VRF <= 1.
- **B — Adaptation-overhead bottleneck:** FreeOracle VRF > 1 while deployed
  M3-G-v1 VRF remains far below 1.
- **C — Accounting inconsistency:** a required headline cannot be reproduced.
- **D — Mixed bottleneck:** FreeOracle is approximately 1 and adaptation
  overhead is also material; both must be quantified.

Verdict selection uses the computed primary endpoint and documented accounting
evidence. It does not authorize a new simulator experiment.

## 8. Completion gates

M3-CA can freeze only if source hashes are unchanged, all 24 states are
retained, all required summaries/figures exist, the minimum M3-CA tests and the
full regression suite pass, `extra_simulator_calls` is zero, exactly one final
verdict is recorded, and claim boundaries are explicit.

Even after completion, M3-CA does not establish universal adaptive superiority,
real-system gain, wall-clock speedup, or generalization beyond the frozen BV2
benchmark and scalar proposal family.
