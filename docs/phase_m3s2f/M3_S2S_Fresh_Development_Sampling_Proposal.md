# M3-S2S Fresh Development Sampling Proposal

Written 2026-09-06T11:48:29+0800 under M3-S2F-R.  **NOT EXECUTED** — this is a design
document; any implementation requires a new taskbook with preregistration,
budget, and human approval.  Zero simulator calls were made here.

## Why

The frozen gradient estimator derives its uncertainty from a stratified
bootstrap over per-sample contribution vectors
(`hyptraj.m3d.adaptation.gradient_decision`: `a_vec`, `resp`, `sq`,
bootstrap seed `[seed, 424243]`, N_BOOTSTRAP replicates).  The trial
records persist only the aggregate `g_hat`, the two CI bounds, ESS_grad and
component summaries — the internal replicate structure that would carry
stability information (batch/bootstrap sign agreement, concentration, LOBO
stability, shape) is discarded at write time.  Reconstruction is only
possible by re-running the sampler, which is a simulator call and therefore
forbidden for feature recovery (M3-S2F-R, not a scientific negative).

## Answers to the ten required questions

1. **New per-trial persistence required**: per-replicate gradient values
   `g_(1..R)` from the stratified bootstrap; per-batch numerator/denominator
   and event counts if a batched (non-bootstrap) variant is adopted; the
   per-sample contribution vector hash (sufficient-statistics fingerprint).
2. **Keep each replicate g**: YES — `bootstrap_g[1..R]` at the frozen
   N_BOOTSTRAP; without it sign agreement / concentration / LOBO are
   undefined.
3. **Batch event counts / ESS**: YES — per-replicate ESS and event counts
   enable dispersion-vs-event-rate attribution of instability.
4. **±Δ local gradient**: YES as an optional arm — persist
   `g(s)`, `g(s+Δ)`, `g(s-Δ)` from the SAME online pilot machinery with a
   preregistered Δ grid candidate set (e.g. ±0.05, ±0.10, ±0.20 in log s²);
   final Δ must be frozen in the S2S preregistration, not chosen here.
5. **Replicates per state**: keep 8 gradient replicates (same as Tier-A) so
   trial-level and state-level stability features remain comparable; add the
   replicate-level stability features described above.
6. **New development states**: generate a fresh state panel from the same
   corrected candidate machinery (CF2-style truth inventory) with the
   round-based config-diversity rule from M3-S1C; target mix ~8W/8S/8ND per
   batch of 24, sized below.
7. **Protected reserve**: the 18 remaining protected states stay excluded by
   construction — new states are drawn only from previously unexposed
   generator cells, and the S1C/PI1VNR/PI1VN panels join the explicit
   exclusion manifest.
8. **Target dataset size**: >= 100 independent states (MLP authorization
   threshold; also stabilizes grouped 5-fold with 20+ configs) across >= 24
   configs.
9. **Budget**: 100 states x 8 replicates x 20k = 16.0M gradient samples
   (+ optional ±Δ arm: 100 x 8 x 2 x 20k = 32.0M if the local-shape family
   is activated; recommend a two-stage gate: stability arm first).
10. **Fields to preregister before any simulator call**: replicate g array
    schema + hashes, per-replicate ESS/event counts, the ±Δ values and arm
    gating rule, panel selection rule, freshness/exclusion manifest, gates
    (coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05), and the
    config-grouped nested-CV threshold rule inherited from M3-ML0/S2F.

## Explicitly out of scope here

No new state generation, no pilot runs, no threshold or Δ freezing, no
confirmation design.  VALUE / RARITY / M3-Q remain BLOCKED.
