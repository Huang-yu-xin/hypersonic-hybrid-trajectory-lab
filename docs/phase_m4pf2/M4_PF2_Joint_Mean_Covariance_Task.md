# M4-PF2 Joint Mean + Covariance Objective-Gradient — Task Lock

> Parent freeze: `RareTopo-M4-PF1-v0`  
> Parent commit: `e6885bb59a8437cd5834a3a60ccf07c9c89624fe`  
> Opening regression: 1,262 passed, 3 pre-existing warnings  
> PF2-0 simulator calls authorized: **zero**

## Scientific question

PF1 showed that rank-1/rank-2 covariance-only objective-gradient updates
improve median FreeOracle VRF by less than one percent and remain near 0.01.
PF2 asks whether proposal mean placement is the dominant remaining source of
absolute inefficiency.

The study keeps objective-gradient control and does not revive descriptive
moment matching.

## Required order

1. Verify the PF1 freeze and source hashes.
2. Complete PF2-0 mean-gradient theory, algebra tests, source audit and anchor
   compatibility with zero simulator calls.
3. Freeze a separate PF2 protocol, state and seed lock.
4. Run a two-state discovery safety validation.
5. Run the full 24-state confirmatory 2x2 experiment.
6. Apply the locked absolute FreeOracle gates and freeze the audit.

## PF2-0 invariant

```text
extra_simulator_calls = 0
```

PF2-0 may read and hash artifacts, derive and test pure arithmetic, and audit
persisted sample fields. It may not generate pilots, trajectories, new seeds,
proposal evaluations or confirmatory results.

If the persisted records do not contain the numeric per-sample quantities
needed for `E_nuV[r_k z_k]`, the required result is:

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
```

If the gradient-source proposal differs from the PF2 anchor and exact
reweighting is unavailable, PF2-0 must record:

```text
FRESH GRADIENT CONSTRUCTION REQUIRED
```

Neither result authorizes simulation before PF2 preregistration is committed.

## Confirmatory design boundary

The primary experiment is limited to:

| Cell | Mean | Rank-1 covariance |
|---|---|---|
| P00 | off | off |
| P10 | on | off |
| P01 | off | on |
| P11 | on | on |

The preferred mean step is 0.20 Mahalanobis units. The covariance step must
reuse PF1 rank-1 semantics exactly: absolute eigenvalue ordering, Frobenius
normalization, `eta_sigma=0.20`, matrix exponential and maximum absolute log
step 0.20. Both gradients are computed at one common anchor and P11 applies
the two updates simultaneously.

The state set remains all 24 frozen M3-BV2 Value-Axis states. The primary
FreeOracle endpoint charges only the selected 100k final arm. All construction,
Oracle search, unselected cells and diagnostics remain audit-only.

## Locked verdicts

- `PF2-A`: median four-cell FreeOracle VRF > 1.
- `PF2-B`: 0.1 < median <= 1.
- `PF2-C`: median <= 0.1.
- `PF2-D`: parent freeze, protocol, baseline, numerical or accounting
  invalidity.

PF2-C routes future work toward separately preregistered mixture allocation or
missing-mode repair, not higher covariance rank. PF3 and M3-Q are outside this
stage.
