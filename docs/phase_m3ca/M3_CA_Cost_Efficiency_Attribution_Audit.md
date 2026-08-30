# M3-CA Cost-Efficiency Attribution Audit

> Status: **COMPLETE — Verdict A**  
> Analysis: existing-artifact arithmetic only  
> Extra simulator calls: **0**  
> Parent result: `RareTopo-M3-BV2-v0`

## 1. Executive conclusion

M3-BV2's relative adaptive-value result reproduces: M3-G-v1 captures
`0.97059066` (97.1%) of the measurable Oracle headroom under the frozen
unified objective. Its absolute budget efficiency also reproduces, with a
median `VRF_budget = 0.00838810`.

Removing all pilot and decision cost raises the M3-G-v1 median only to
`0.01006572`. More importantly, making the Oracle action free raises the
median only to `0.01005324`, still roughly two orders of magnitude below the
cost-efficiency boundary `VRF = 1`. None of the 24 frozen Value-Axis states has
FreeOracle VRF above 1; the observed range is `0.00520610–0.02041722`.

The preregistered primary diagnostic therefore answers:

```text
VRF_budget_free_oracle > 1 ?  NO
```

The final verdict is **A — proposal / benchmark-regime bottleneck**. Within
the frozen BV2 benchmark and scalar proposal family, even perfect free action
selection cannot deliver absolute cost efficiency. Pilot/adaptation overhead
is real but is not sufficient as the main explanation.

## 2. Live Git and BV2 freeze audit

The start-of-stage audit recorded:

| Item | Live result |
|---|---|
| branch | `feature/phase-m3bv2-dual-axis-benchmark` |
| starting HEAD | `912ed9771c34c50cc05825c7a5f3590553b5dfb0` |
| M3-G-v1 peeled commit | `4505a36265ac3020d4b31290c697f7fb37fe2e07` |
| M3-BV-v0 peeled commit | `1eea1836ae48831dc102f878dddbbb9268aefdcd` |
| BV2 Decision/Value freeze commit | `2e814a5` |
| BV2 controller result commit | `9b68ec9` |
| BV2 completed artifact commit | `912ed97` |
| live pre-analysis regression | `1216 passed, 3 warnings`, exit 0 |
| `RareTopo-M3-BV2-v0` before CA0 | missing |
| `RareTopo-M3-BV2-v0` after CA0 | local annotated tag at `912ed97` |

The three pytest warnings are existing `PytestRemovedIn10Warning` notices for
class-scoped instance fixtures. They do not affect the current pass result.

The worktree contained unrelated pre-existing untracked archives, an H3 paper
directory, and non-M3-CA figure content. They were preserved and never staged
or modified by M3-CA. No pre-existing untracked path overlapped
`docs/phase_m3ca`, `configs/phase_m3ca`, `src/hyptraj/m3ca`,
`results/phase_m3ca`, or `figures/phase_m3ca`.

## 3. Source lock and provenance

`results/phase_m3ca/summary/m3ca_source_manifest.json` records 16 source
artifacts with path, SHA-256, source stage/tag, role, and read-only status.
The lock includes BV2 controller/value/decision/reuse records, BV-v0 candidate
and headline records, both BV2 freezes/configs, M3-D and M3-G-v1 protocols and
records, and the M1-D benchmark freeze containing stored event probabilities.

All source hashes were computed before arithmetic and recomputed after output
generation. Result:

```text
sources_unchanged = true
post_analysis_mismatches = []
```

The analysis entry point imports only M3-CA arithmetic/provenance code. Static
tests reject simulator, pilot-generation, state-assembly, proposal-evaluation,
and RNG entry points.

## 4. Cost-accounting reconstruction

The deployable simulator-call cost is

\[
C_{deploy}=C_{pilot}+C_{decision}+C_{selected}.
\]

The frozen protocol records:

| Method | Pilot | Decision simulator calls | Selected arm | Deployable total |
|---|---:|---:|---:|---:|
| CrudeMC | 0 | 0 | 100,000 | 100,000 |
| BASE/fixed rule/BestFixed | 0 | 0 | 100,000 | 100,000 |
| FreeOracle | 0 | 0 | 100,000 | 100,000 |
| M3-D | 20,000 | 0 | 100,000 | 120,000 |
| M3-G-v1 | 20,000 | 0 | 100,000 | 120,000 |
| FreeAdaptation | 0 | 0 | 100,000 | 100,000 |

The decision rule has no separately recorded simulator calls. Its CPU or
wall-clock cost is **NOT IDENTIFIABLE FROM EXISTING ARTIFACTS** and is not
silently treated as a measured wall-clock zero.

The 500k × 3-arm reference characterization and 8 × 100k × 3-arm headline
characterization are recorded in the ledger as shared audit-only costs. They
are excluded from every deployable VRF. Oracle discovery, counterfactual arms,
all-fixed comparisons, figures and reports are likewise audit-only.

### Probability-field limitation

The frozen 100k fixed-arm characterization streams preserve replicate M2 but
not replicate `P_hat`. Therefore BestFixed and FreeOracle VRFs use the existing
500k reference-arm `P` paired with each stored 100k replicate M2. This
convention is explicit in every relevant ledger/state row. No `P_hat` was
invented and no arm was rerun. The deployed M3-G-v1 headline uses its stored
replicate `arm_P_hat` and reproduces the original recorded VRF exactly.

## 5. Headline reproduction gate

Using

\[
J(\pi)=\operatorname{median}_{state}\left[
\operatorname{median}_{rep}\log\frac{M_2(\pi)}{M_2(BASE)}\right],
\]

the independent reconstruction gives:

| Quantity | Recomputed |
|---|---:|
| `J(ALWAYS_WIDEN)` | −0.014791285 |
| `J(ALWAYS_SHRINK)` | +0.022430941 |
| `J(ALWAYS_HOLD)` | 0 |
| `J(Oracle)` | −0.068943300 |
| `J(M3-D)` | −0.067350725 |
| `J(M3-G-v1)` | −0.067350725 |
| BestFixed | ALWAYS_WIDEN |
| `G_Oracle` | 0.054152015 |
| `G_v1` | 0.052559440 |
| Capture | 0.970590660 |
| M3-G-v1 median `VRF_budget` | 0.008388097 |
| M3-D/M3-G-v1 Value action parity | true |

All locked headline checks pass. Stored selected-arm VRFs also reproduce from
their source M2/P/budget values with maximum absolute difference below
`1e-15`. Scientific attribution was therefore allowed to proceed; Verdict C
does not apply.

## 6. Counterfactual efficiency audit

| Method/counterfactual | Across-state median VRF budget |
|---|---:|
| CrudeMC | 1.00000000 |
| BASE | 0.00929195 |
| BestFixed | 0.00914965 |
| FreeOracle | 0.01005324 |
| M3-D | 0.00838810 |
| M3-G-v1 | 0.00838810 |
| FreeAdaptation | 0.01006572 |

FreeAdaptation is exactly the same stored M3-G-v1 arms with the 20k pilot
removed from budget accounting, so its replicate VRFs are 1.2 times deployed
VRFs. This increase is far too small to approach 1.

FreeOracle is a non-deployable accounting counterfactual. It selects the
frozen Oracle arm for free and pays only the final 100k evaluation cost. Its
median is also about 0.01. Hence perfect action selection does not rescue the
current proposal family.

The fact that FreeAdaptation is marginally above FreeOracle at the aggregate
median is not interpreted as superiority over Oracle. The quantities combine
different stored probability-field conventions, and medians need not preserve
pointwise ordering. The decisive result is robust to this nuance: both are far
below 1, and every state-level FreeOracle VRF is below 0.021.

## 7. Efficiency ladder

The log-scale ladder is:

```text
CrudeMC (1.0)
  -> BestFixed (0.00915)
  -> FreeOracle (0.01005)
  -> M3-G-v1 (0.00839)
```

This ladder is descriptive rather than an exact causal additive
decomposition. It shows that the absolute-efficiency loss is already present
before controller overhead is introduced. The Oracle switching benefit is
real relative to BestFixed, but tiny compared with the approximately 100-fold
gap to crude MC.

## 8. Class and 24-state audit

All 24 frozen Value-Axis states are retained:

```text
WIDEN = 12
SHRINK = 12
HOLD = 0
states removed = 0
```

Class medians are:

| Class | BestFixed | FreeOracle | M3-D | M3-G-v1 | FreeAdaptation |
|---|---:|---:|---:|---:|---:|
| WIDEN | 0.00877173 | 0.00877173 | 0.00731635 | 0.00731635 | 0.00877962 |
| SHRINK | 0.01151497 | 0.01351276 | 0.01125722 | 0.01125722 | 0.01350866 |

SHRINK states contain the adaptive headroom relative to globally best fixed
ALWAYS_WIDEN, consistent with BV2. However, their higher FreeOracle median is
still only 0.0135. All 24 states are classified `INEFFICIENT` by the locked
FreeOracle > 1 rule.

The complete per-state table is saved at
`results/phase_m3ca/summary/m3ca_state_table.csv`. It includes config, `s2`,
class/actions, M2 values, proposal/budget VRFs, pilot fraction, reference
leakage concentration, Oracle loss, and efficiency class. BV2 controller
records did not preserve per-state ESS or pilot `M2_hat`; these columns are
marked **NOT IDENTIFIABLE FROM EXISTING ARTIFACTS**.

## 9. Difficulty and pilot audit

Overall descriptive Spearman associations with FreeOracle VRF are:

| Existing field | rho | p-value | Interpretation boundary |
|---|---:|---:|---|
| event probability | +0.7645 | 1.36e−5 | positive rank association |
| BASE median M2 | −0.7652 | 1.32e−5 | negative rank association |
| reference leakage concentration | +0.1139 | 0.596 | no clear rank association |
| `s2` | +0.4335 | 0.0343 | moderate rank association |

These are descriptive patterns on the constructed frozen state set. They do
not establish causal mechanisms or generalization.

The pilot fraction is fixed for every controller state:

\[
f_{pilot}=20{,}000/120{,}000=1/6=0.1666667.
\]

Because it has no cross-state variation, its correlation with VRF is not
identifiable. No 20k→10k or 20k→5k pilot experiment was run.

## 10. Figures

Eight required figures are present under `figures/phase_m3ca/`:

1. CA-1: proposal VRF versus budget VRF;
2. CA-2: CrudeMC/BestFixed/FreeOracle/M3-D/M3-G-v1 ladder;
3. CA-3: deployed versus FreeAdaptation;
4. CA-4: BestFixed/FreeOracle/M3-G-v1 primary comparison;
5. CA-5: WIDEN/SHRINK class decomposition;
6. CA-6: all 24 state-level efficiencies;
7. CA-7: fixed pilot-fraction audit;
8. CA-8: adaptive headroom capture versus absolute efficiency.

All efficiency figures include the `VRF = 1` reference. CA-6 retains every
state. CA-8 explicitly marks WIDEN states with zero available Oracle headroom
rather than assigning a fabricated capture ratio.

## 11. Test and freeze evidence

The M3-CA-specific suite contains 18 tests covering the zero-simulator
firewall, source hashes, source-manifest completeness, deployable/audit cost
separation, exact VRF and headroom reconstruction, all counterfactual formulas,
BestFixed cost semantics, action parity, 24-state retention, 12/12 class split,
and output schemas. Targeted result:

```text
18 passed
```

The final repository-wide regression, after code, tables, audit and figures
were generated, produced:

```text
1234 passed, 3 warnings in 839.68s
exit code = 0
```

The warnings are the same pre-existing pytest fixture deprecation notices
recorded in CA0. No M3-CA warning or failure occurred.

Final freeze checks:

```text
source hashes unchanged = true
extra_simulator_calls = 0
headline reproduction = PASS
24 states retained = PASS
WIDEN/SHRINK split = 12/12 PASS
required figures = 8/8
summary JSON/CSV = complete
full regression = PASS
```

## 12. Final verdict and next stage

```text
FINAL VERDICT: A — PROPOSAL / REGIME BOTTLENECK
```

Within the frozen BV2 benchmark and scalar proposal family, near-Oracle
adaptive action selection does not translate into absolute cost efficiency.
The primary bottleneck lies upstream in proposal-family or benchmark-regime
efficiency rather than in action selection or pilot overhead alone.

The next scientific stage, if authorized separately, should be a newly
preregistered proposal-family redesign study. Candidate directions may include
structured/diagonal/low-rank covariance actions, component-specific control,
joint mean-covariance objective-gradient control, mixture allocation redesign,
or missing-mode repair. M2's negative result remains binding: descriptive
local variance geometry is not by itself a valid covariance-control target.

M3-Q remains blocked. Curvature has not been established as the dominant
remaining bottleneck.

## 13. Claim boundaries

This audit supports only a statement conditioned on the frozen BV2 benchmark
and frozen scalar proposal family. It does not establish:

- universal adaptive superiority;
- real-system or wall-clock speedup;
- generalization to unseen event geometries;
- that 97.1% relative headroom capture means 97.1% efficiency versus crude MC;
- that full-matrix covariance control or proposal-family efficiency is solved;
- that M3-Q is necessary.

The central distinction is:

```text
relative adaptive value != absolute budget efficiency
```
