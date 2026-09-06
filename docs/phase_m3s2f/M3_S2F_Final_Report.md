# M3-S2F Final Report

Verdict: **M3-S2F-R** (2026-09-06T11:48:29+0800).  gradient-stability features not recoverable from Tier-A artifacts without simulator replay; recoverability gate precedes models.

This is a **recoverability / instrumentation result, not a scientific
negative**: the exposed Tier-A artifacts (48 states / 384 trials, dataset
sha256 `f5f684fdb693123c...`) persist only the aggregate gradient
`g_hat`, the two CI bounds, `ESS_grad` and component summaries.  None of
the nine required batch/bootstrap-level families (per-batch g, per-batch
numerator/denominator, batch signs, batch ESS, batch event counts,
contribution statistics, CRN batch ids, bootstrap replicates, per-sample
sufficient statistics) is present on any of the 384 trials
(`m3s2f_recoverability_matrix.csv`, 384/384 rows audited).  The stability
hypothesis (taskbook Sec. 6) is therefore UNTESTED, not refuted.

- Family A (gradient stability): NOT_RECOVERABLE (replay required => INCOMPATIBLE).
- Family B (practical margin M_delta): constructible from persisted g_hat/SE
  alone, but its standalone evaluation without the stability family was out
  of this stage's scope; carried into the S2S proposal as a preregistered
  candidate.
- Family C (local shape): NOT_AVAILABLE for primary use (PI1VNR-only probe
  cannot be mixed with S1C no-probe trials; taskbook Sec. 8.1).

Recoverability gate precedence (Sec. 15) applied: models were NOT run, no
proxy/imputation/replay was used, and the M3-S2S fresh-sampling proposal
was written instead (see `M3_S2S_Fresh_Development_Sampling_Proposal.md`;
NOT executed).

- New simulator calls: **0**.  New samples: **0**.
- Protected reserve: 18 states; used: **0** (membership-only audit).
- Tier-A dataset hash re-verified: **match**.

## Claim boundary

Allowed: "Existing exposed artifacts do not contain sufficient batch-level
online information to test the proposed stability hypothesis without new
sampling."  Not allowed: "stability features don't help", "confirmed",
"deployment safe".  VALUE / RARITY / M3-Q remain BLOCKED.
