# M3-S25-R1-A2R-B0 CRN Audit (B0.1 corrected)

Recorded during B0.1 CRN-semantics amendment. Parent terminal:
M3-S25-R1-A2R-B-GATE at `5d7eb7b234cedb0069adf7043234047a34028288`.

## 1. Question

Does using the frozen center seed as the CRN anchor at `u-Delta`, `u`,
`u+Delta` (where `u = log(s^2)` and `Delta = 0.10`) really give the
intended common-random-number coupling?

## 2. RNG Implementation Audited

**File**: `src/hyptraj/m3d/adaptation.py`

```python
def draw_online_pilot(st, seed, n_pilot=20000, alpha=0.5):
    prop = st.proposal()
    rng = np.random.default_rng([int(seed), 101])
    z, logr, strata = draw_mix_pilot(rng, prop, st.bench_cfg.logp,
                                     int(n_pilot), float(alpha))
    logp = np.asarray(st.bench_cfg.logp(z), dtype=float)
    return z, logp, np.asarray(logr, dtype=float), np.asarray(strata)
```

**File**: `src/hyptraj/m1d/adaptation.py`

```python
def draw_mix_pilot(rng, proposal, logp_fn, n, alpha=0.5):
    n_p = int(round(n * alpha))   # 10000 target-source
    n_q = n - n_p                  # 10000 proposal-source
    d = proposal.centers.shape[1]
    zp = rng.standard_normal((n_p, d))         # step 1
    rp = logp_fn(zp)
    zq = proposal.sample(rng, n_q)             # step 2+3
    rq = proposal.log_density(zq)
    z = np.vstack([zp, zq])
    logr = np.concatenate([rp, rq])
    strata = np.concatenate([np.zeros(n_p, dtype=int), np.ones(n_q, dtype=int)])
    return z, logr, strata
```

**File**: `src/hyptraj/m2/covariance_policy.py`

```python
def sample(self, rng, n):
    comp = rng.choice(self.n_components, size=n, p=self.weights)  # step 2
    eps = rng.standard_normal((n, d))                              # step 3
    chols = self.chols
    transformed = np.einsum("njk,nk->nj",
                            np.stack([chols[c] for c in comp]), eps)
    return self.centers[comp] + transformed
```

**File**: `src/hyptraj/m3d/benchmark_states.py`

```python
def proposal(self):
    covs = list(self.covs_other)
    covs.insert(self.component_index, self.s2 * np.eye(self.dim))
    # centers and weights are FROZEN, independent of s2
```

## 3. RNG Consumption Analysis

The RNG `[seed, 101]` is consumed in this order:

| Step | Operation | RNG calls | Depends on s2? |
|------|-----------|-----------|----------------|
| 1 | `rng.standard_normal((10000, d))` | 10000*d | NO |
| 2 | `rng.choice(components, n=10000, p=weights)` | ~10000 | NO (weights frozen) |
| 3 | `rng.standard_normal((10000, d))` | 10000*d | NO |

**Key finding**: The raw RNG output is IDENTICAL regardless of `s2`.
The RNG sequence is fully determined by the seed. Same seed gives:
- Same component choices (step 2)
- Same base Gaussian epsilons (step 3)

## 4. Where s2 Enters

`s2` enters through the **Cholesky transformation** in `proposal.sample()`:

```python
chols[selected_component] = sqrt(s2) * I   # since cov = s2 * I
transformed = chols[c] @ eps               # eps is SAME, but chols differs
zq = centers[comp] + transformed           # zq is DIFFERENT
```

- `eps` (raw Gaussian) is the SAME for all `s2` values
- `chols[selected_component] = sqrt(s2) * I` changes with `s2`
- Therefore `zq` (proposal-source samples) is DIFFERENT for different `s2`

## 5. CRN Semantics (Corrected in B0.1)

**CORRECTED**: `CRN = shared underlying RNG / center seed`, NOT `identical z`.

Same seed across center/left/right gives the same component choices and
base Gaussian epsilons. Different s2 changes the deterministic Cholesky
transform, so different z is expected and is still paired CRN.

The CRN coupling is through the SHARED underlying RNG sequence, not
through identical output arrays. This is standard paired CRN practice:
the same random seeds drive the same stochastic process, but the
deterministic transformation differs across parameter values.

## 6. Implementation (Corrected in B0.1)

For each center logical unit with frozen center seed `seed_c`:

1. Construct left state: `s2_left = s2_center * exp(-0.10)`
2. Construct right state: `s2_right = s2_center * exp(+0.10)`
3. Left: `z_L, logp_L, logr_L, strata_L = draw_online_pilot(st_left, seed_c)`
4. Right: `z_R, logp_R, logr_R, strata_R = draw_online_pilot(st_right, seed_c)`
5. Each side runs the full frozen gradient pipeline with its OWN z, logp, logr, strata
6. Center is NEVER rerun

## 7. What Is FORBIDDEN

- Drawing center once and reusing center z for side gradients
- Replacing center logr by side proposal density
- Reusing center a_vec, resp, or sq for a side estimator
- Using independent RNG for side evaluations
- Silent switch to non-CRN approach

## 8. Feasibility Proof

For all 120 panel states:
- `s2_side = s2 * exp(+-0.10)` ranges from 0.495 to 8.803
- All `s2_side > 0` (valid for Cholesky decomposition)
- All `s2_side` within reasonable numerical range
- **Verdict**: 120/120 states feasible for Delta=0.10

## 9. Conclusion

**CRN IS achievable** with the frozen RNG implementation. The approach is:
for each center unit, construct left/right side states with modified s2,
call `draw_online_pilot` independently for each side using the center
seed as CRN anchor, and run the full frozen gradient pipeline with each
side's own returned arrays.

`ARM_B_ELIGIBLE = YES` (CRN semantics verified and corrected, feasibility confirmed)
