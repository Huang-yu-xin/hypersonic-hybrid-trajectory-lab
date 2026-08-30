# M4-PF2 Joint Mean–Covariance Objective-Gradient Audit

## 1. Status and verdict

M4-PF2 is complete on the 24 frozen M3-BV2 Value-Axis states. The
preregistered one-step `2 x 2` experiment passed its parent-freeze,
reproduction, numerical-safety, tail-safety and accounting gates.

The primary FreeOracle median budget VRF is

\[
0.0128305759044 \le 0.1,
\]

so the locked scientific verdict is:

```text
PF2-C — JOINT MEAN/COVARIANCE STILL INSUFFICIENT
```

Mean translation improves every frozen state in both factorial contrasts,
but the gain is small relative to the remaining absolute-efficiency gap. The
result does not support proposal-centre placement as the missing approximately
`100x` mechanism under this locked one-step family.

## 2. Parent and provenance audit

- PF1 tag: `RareTopo-M4-PF1-v0`
- PF1 peeled commit: `e6885bb59a8437cd5834a3a60ccf07c9c89624fe`
- PF1 verdict: `PF1-C`
- PF1 retained states: 24
- PF1 protocol SHA-256:
  `70f230e2926d47609aa2486489c30821a737e5f2baa2c37d0b8d401a15f71dc5`
- PF1 states SHA-256:
  `79795ff146daee0860217aadb715f594176f9687e07da52c5bf82ef8afaed88e`
- PF1 seeds SHA-256:
  `a568eb45196c665ae5fdee522cf2b7d56fa53df0b19f9bbe3d909aa29a96ecc8`
- M3-BV2 state-source SHA-256:
  `fa42d60d4dc78330cdf6fc99cf68f5f81a1986588c6aeb1d25edded17525225c`

The opening full regression passed with `1262 passed` before PF2 changes.
Unrelated pre-existing working-tree files were not modified.

## 3. PF2-0 zero-simulator audit

PF2-0 made zero simulator calls. It established the dimensionless mean
quantity

\[
a_k=E_{\nu_V}[r_kz_k]
\]

and the Euclidean objective gradient

\[
\nabla_{\mu_k}M_2=-M_2\Sigma_k^{-1/2}a_k.
\]

Consequently, `+a_k` is the descending direction in whitened mean
coordinates. A deterministic analytic Gaussian central-difference fixture
matched the theoretical derivative with maximum relative error approximately
`1.31e-10`; descent-sign and coordinate-scaling checks also passed.

The PF1 artifacts do not contain the per-sample arrays required to reconstruct
the first moment exactly. Moreover, PF1 constructed gradients at the base
proposal, whereas PF2's preferred anchor is the per-state S0-selected
widen/shrink proposal. The mismatch occurs in `24/24` states, and exact
reweighting is impossible from the persisted aggregates. PF2-0 therefore
locked both findings:

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
FRESH GRADIENT CONSTRUCTION REQUIRED
```

The PF2-0 source manifest contains 11 read-only sources whose before/after
hashes agree. This phase is frozen by tag `RareTopo-M4-PF2-0-v0`.

## 4. Preregistered confirmatory protocol

The protocol, state list and all seeds were committed before any PF2 discovery
or confirmation data:

- states: 24 (`12 WIDEN`, `12 SHRINK`, `0 HOLD`)
- common anchor: frozen per-state S0 FreeOracle-selected scalar proposal
- factorial cells: P00, P10, P01 and P11 only
- fresh gradient construction: four `100,000`-sample streams per state
- mean step: `0.20` Mahalanobis units
- numerical-zero threshold: `1e-12`
- covariance update: PF1 rank-1, Frobenius-normalized matrix exponential
- covariance step: `eta_sigma = 0.20`
- maximum absolute log step: `0.20`
- minimum eigenvalue guard: `0.5`
- condition-number ceiling: `4`
- joint convention: both gradients evaluated at the common anchor and both
  updates applied simultaneously, with no within-step recomputation
- confirmation: eight paired CRN replicates per state and cell
- final-arm budget: `100,000` samples per replicate
- probability characterization: `500,000` new samples for P10/P01/P11
- FreeOracle tie order: P00, P10, P01, P11
- seed separation: PF2 discovery, PF2 confirmation and PF1 streams are
  disjoint

Locked PF2 hashes:

| File | SHA-256 |
|---|---|
| `m4pf2_protocol.json` | `f871b8268b27429d07731e0a2019ae11f2770274e77eaa1a9f22092369d3cee1` |
| `m4pf2_states.json` | `fb3879b772bdf3ac461355ccc93395cf3a542844bf868fc2968f6b51da3825ae` |
| `m4pf2_seeds.json` | `330a9b495767d435da50f4e1ca7765c5d71f75d5e40903eb0787b532b1cee0b9` |

PF2-D used one WIDEN and one SHRINK state only for implementation and safety
validation. It passed without a protocol change; its minimum ESS exceeded
`1185`, mean-step norms were `0.20`, and covariance condition numbers were
approximately `1.2214`.

## 5. Confirmatory cell results

Higher VRF is better. “States >” entries are counts out of 24.

| Cell | Mean | Cov rank-1 | Median VRF | States >0.1 | States >1 | Worst-state VRF | WIDEN median | SHRINK median |
|---|---|---|---:|---:|---:|---:|---:|---:|
| P00 | OFF | OFF | 0.010079927152 | 0 | 0 | 0.005104274182 | 0.008764714014 | 0.013518656501 |
| P10 | ON | OFF | 0.011491144816 | 0 | 0 | 0.006138723924 | 0.010285406918 | 0.015272191475 |
| P01 | OFF | ON | 0.010894224188 | 0 | 0 | 0.006318169373 | 0.010244502259 | 0.014415831282 |
| P11 | ON | ON | 0.012830575904 | 0 | 0 | 0.007515379593 | 0.012242705275 | 0.016356780627 |

P00 reproduces the frozen PF1 S0 anchor: its median is `0.010079927152`
versus `0.010053236114` in PF1, a relative difference of `0.2655%`, which
passes the preregistered `10%` independent-stream tolerance.

FreeOracle selects P11 in all 24 states. Its headline median equals the P11
median, `0.012830575904`; this is `27.29%` above the P00 median but still about
`78x` below VRF 1.

## 6. Factorial mechanism contrasts

The locked statewise median log-VRF contrasts are:

| Contrast | Median log contrast |
|---|---:|
| Mean without covariance: log(P10/P00) | 0.129604108853 |
| Mean with covariance: log(P11/P01) | 0.136166028527 |
| Covariance without mean: log(P01/P00) | 0.068840747878 |
| Covariance with mean: log(P11/P10) | 0.073210766802 |
| Descriptive interaction | -0.002967705867 |

Mean improves `24/24` states without covariance and `24/24` states with
covariance; it worsens `0/24` and is neutral in `0/24`. Thus translation has a
consistent local effect and is stronger than the rank-1 covariance main
effect. The interaction is nearly zero, so this experiment does not reveal a
large mean/covariance synergy. These are locked factorial contrasts on the
constructed benchmark, not a universal causal decomposition.

## 7. Gradient, geometry and safety

- median aggregate mean-gradient norm: approximately `0.543454`
- state range of aggregate mean-gradient norms: `0.212181` to `0.919426`
- Euclidean mean-displacement range: `0.178203` to `0.511853`
- nonzero Mahalanobis displacement: `0.20` by construction
- updated covariance condition number: approximately `1.221403`
- minimum confirmatory ESS: `8392.094`
- maximum normalized importance weight: `0.0030392`
- nonfinite weight count: 0
- event-weight underflow count: 0
- support-loss indicators: none
- fallback count: 0

All 24 persisted fresh-gradient archives contain proposal identity, gradient
seeds, samples, variance mass, responsibilities, whitened coordinates and
source strata. Their SHA-256 values are locked in the final source manifest.
The archives total approximately `442 MB` and make the PF2 gradient
construction auditable without rerunning the simulator.

## 8. Cost accounting

The counterfactual deployable FreeOracle endpoint charges only the selected
`100,000`-sample final arm. Construction and proposal search are not hidden:

| Cost category | Simulator samples |
|---|---:|
| Deployable selected arm, per state | 100,000 |
| Confirmation audit-only scientific cost | 122,400,000 |
| Discovery audit-only scientific cost | 200,000 |
| Total actual PF2 scientific cost | 122,600,000 |

The deployable number is a proposal-family feasibility denominator, not a
claim that FreeOracle selection or gradient construction is free in practice.

## 9. Interpretation and claim boundary

Under the frozen BV2 state family, current mixture parameterization, common S0
anchor, locked `0.20` one-step mean translation, locked rank-1 covariance
update and FreeOracle accounting, mean movement helps consistently but does
not materially repair absolute cost efficiency. Increasing covariance rank is
already excluded by PF1 and is not justified by PF2.

PF2 does **not** establish that all mean control must fail, that FreeOracle is
deployable, that mixture allocation is definitely causal, or that the result
generalizes to unseen event families. It tests exactly one preregistered local
proposal family.

The scientific next stage suggested by PF2-C is a separately preregistered
M4-PF3 study of mixture allocation and missing-mode repair. PF3 was not
implemented or executed here. M3-Q remains blocked.

## 10. Reproducibility outputs

The final package includes:

- frozen configs in `configs/phase_m4pf2/`
- raw discovery and confirmation records in `results/phase_m4pf2/raw/`
- 24 compressed gradient archives in
  `results/phase_m4pf2/gradient_samples/confirmation/`
- final manifests and tabular summaries in `results/phase_m4pf2/summary/`
- twelve required figures in `figures/phase_m4pf2/`
- experiment, provenance and analytic-gradient tests in `tests/`

The closing full-repository regression result and final freeze tag are recorded
after this audit is committed.
