# M4-PF1 Structured Proposal Audit

## 1. Final status

**M4-PF1 is complete with verdict `PF1-C`: covariance-only expressiveness is
insufficient.**

The best structured family was S1, with median absolute FreeOracle budget VRF
`0.010119621546`. This is only `0.6603%` above the exactly reproduced S0
anchor (`0.010053236114`) and remains nearly tenfold below the material gate
`0.1` and about hundredfold below absolute efficiency at `1`. S2 reached
`0.010108626406`, a `0.5510%` increase over S0.

No state crossed `VRF = 0.1` or `VRF = 1` under S1 or S2. The preregistered
rule therefore blocks mechanical covariance-rank escalation and routes any
future work to a separately preregistered joint mean-plus-covariance study.

## 2. Freeze and protocol

- PF0 parent: `RareTopo-M4-PF0-v0` at
  `a18a6a5a5f501ba236c2541e83b659d8d6cca021`.
- PF1 preregistration commit: `b36a5f5`.
- Implementation-before-data commit: `68d1ed4`.
- Families: frozen S0 scalar baseline, S1 rank-1 objective gradient, S2
  rank-2 objective gradient.
- States: all 24 frozen M3-BV2 Value-Axis states, split 12 WIDEN / 12 SHRINK.
- Gradient reference: four independent 100k mixed-pilot streams per state,
  pooled only for the matrix-gradient construction.
- Update: absolute-eigenvalue ordering, rank truncation, Frobenius
  normalization, common `eta = 0.20`, matrix exponential, maximum absolute
  log step `0.20`.
- Confirmation: eight paired 100k evaluation replicates per state and arm,
  using the frozen full-grid CRN keys.
- FreeOracle deployable cost: selected 100k final arm only; gradient
  construction, probability characterization, unselected arms and Oracle
  search are audit-only.

The committed lock hashes recorded in the raw output are:

- protocol: `70f230e2926d47609aa2486489c30821a737e5f2baa2c37d0b8d401a15f71dc5`;
- states: `79795ff146daee0860217aadb715f594176f9687e07da52c5bf82ef8afaed88e`;
- seeds: `a568eb45196c665ae5fdee522cf2b7d56fa53df0b19f9bbe3d909aa29a96ecc8`.

The frozen M3-BV2 state source hash remained
`fa42d60d4dc78330cdf6fc99cf68f5f81a1986588c6aeb1d25edded17525225c`.

## 3. Discovery validation

The locked discovery stage used one WIDEN and one SHRINK state with disjoint
seeds. Both passed finite-weight, SPD, minimum-eigenvalue, condition-number and
tail-schema checks. The observed structured covariance condition numbers were
about `1.216--1.230`; no log-step clipping or base fallback occurred.

Discovery did not alter any protocol field, rank, eta, state, seed, budget,
metric or success gate.

## 4. Scalar reproduction gate

The S0 replay matched the frozen M3-BV2 per-replicate M2 records with maximum
absolute error `4.9997e-10`. Its median FreeOracle budget VRF was
`0.010053236113979486`, differing from the M3-CA anchor
`0.010053236113756588` by only `2.2290e-13`.

The scalar reproduction gate therefore passed. This rules out a changed event
definition, draw order, probability convention or budget formula as the cause
of the structured result.

## 5. Primary and secondary results

| Family | Rank | Median FreeOracle VRF | States >0.1 | States >1 | Worst state | WIDEN median | SHRINK median |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | 0 | 0.01005324 | 0/24 | 0/24 | 0.00520610 | 0.00877173 | 0.01351276 |
| S1 | 1 | 0.01011962 | 0/24 | 0/24 | 0.00523325 | 0.00888659 | 0.01339734 |
| S2 | 2 | 0.01010863 | 0/24 | 0/24 | 0.00523268 | 0.00889887 | 0.01341279 |

The structured arm beat its own base candidate in all 24 states for both S1
and S2, so the FreeOracle containment rule selected it everywhere. Against the
stronger S0 scalar Oracle, however, only 13 states improved and 11 worsened.
The median structured/S0 M2 ratios were `0.996414` for S1 and `0.996433` for
S2. Thus the directional degrees of freedom produced a detectable but
scientifically immaterial local gain.

## 6. Directional mechanism findings

The newly persisted sample data made the real-state matrix gradient
identifiable. Across the 24 states:

- median anisotropy score: `1.4017` (range `1.0386--1.7659`);
- median cancellation score: `0.001209` (range approximately `0--0.3129`);
- median top-1 absolute spectral fraction: `0.9075` (range
  `0.6403--0.9988`);
- top-2 fraction: exactly one in the two-dimensional benchmark up to floating
  precision.

The gradient was often spectrally concentrated, which justified the locked
rank-1 comparison. But the proposed core mechanism—large opposing eigenvalues
hidden by scalar trace cancellation—was not typical: median sign cancellation
was nearly zero. Rank two did not outperform rank one. Directional covariance
structure therefore exists, but it is not the missing mechanism capable of
closing the absolute-efficiency gap on this benchmark.

This is an intervention result for the locked objective-gradient updates, not
a universal causal claim about anisotropy.

## 7. Numerical and tail safety

All 24 states and both structured families passed numerical safeguards.

- Confirmatory structured condition-number range: `1.0794--1.2625`.
- No nonfinite importance weights.
- No event-weight underflows.
- No unsafe-update fallback.
- Median selected-arm ESS: S0 `17370.6`, S1 `17730.6`, S2 `17748.5`.
- Maximum normalized weight over all selected-arm replicates: S0 `0.002977`,
  S1 `0.002548`, S2 `0.002547`.

The failure to cross either efficiency gate is therefore not attributable to
SPD failure, a condition-number rejection or an obvious weight-tail collapse.

## 8. Cost accounting

The primary FreeOracle counterfactual charges exactly 100k selected-arm calls
per state/family, with pilot and decision cost zero. Actual scientific calls
are segregated as audit-only:

- confirmation gradient construction: 9.6 million samples;
- S0 CRN/tail replay: 57.6 million;
- S1 characterization and evaluation: 31.2 million;
- S2 characterization and evaluation: 31.2 million;
- discovery validation: 0.12 million.

Total actual PF1 simulator sample evaluations were 129.72 million. They are
not added to the FreeOracle deployable denominator because the endpoint
deliberately isolates proposal-family feasibility. The cost ledger records
shared gradient construction once, preventing double counting across S1/S2.

## 9. Figures

The required result figures are under `figures/phase_m4pf1/`:

1. `PF1-1_freeoracle_vrf_by_family.png`;
2. `PF1-2_s0_vs_s1_statewise_vrf.png`;
3. `PF1-3_s0_vs_s2_statewise_vrf.png`;
4. `PF1-4_24_state_log_vrf.png`;
5. `PF1-5_class_conditional_vrf.png`;
6. `PF1-6_vrf_gain_vs_anisotropy.png`;
7. `PF1-7_vrf_gain_vs_spectral_mass.png`;
8. `PF1-8_ess_tail_risk.png`;
9. `PF1-9_efficiency_gate.png`;
10. `PF1-10_structured_covariance_examples.png`.

Every absolute-efficiency figure includes the `VRF = 1` reference, and the
family/gate figures also identify the material `VRF = 0.1` threshold.

## 10. Verdict and claim boundary

The locked verdict is:

```text
PF1-C
COVARIANCE-ONLY EXPRESSIVENESS INSUFFICIENT
```

Increasing covariance directional expressiveness from S0 to a one-step
rank-1 or rank-2 objective-gradient proposal does not recover enough absolute
efficiency to justify rank-4, rank-8 or free full-matrix escalation. This does
not mean the matrix gradient is incorrect, nor that M3 scalar control was
wrong; it means covariance shape alone is not the dominant remaining gap in
the frozen regime.

The next permissible scientific stage is a separately preregistered M4-PF2
joint mean-plus-covariance objective-gradient study. PF2 is not executed here.
`M3-Q` remains blocked.

