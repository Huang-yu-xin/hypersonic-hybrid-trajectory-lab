# M3-S2F Recoverability Audit

Status: **INCOMPATIBLE** (2026-09-06T11:48:29+0800); per-trial bitsets in
`results/phase_m3s2f/preflight/m3s2f_recoverability_matrix.csv` (384/384).

- Nine required batch/bootstrap-level families audited against the actual
  nested schema of every exposed trial record: **0/9 present on 0/384
  trials**.  `gradient.batches` is the constant configuration value 20, not
  per-batch data; the only persisted uncertainty summary is the 2-number CI
  (g_ci_low, g_ci_high).
- The estimator's internal structure (per-sample contribution vectors and
  stratified-bootstrap replicate gradients, seed [seed, 424243]) is computed
  and discarded at write time; reconstruction requires re-running the
  sampler => simulator call => INCOMPATIBLE (taskbook Sec. 3.3).
- Classification: **INCOMPATIBLE** (recoverability gate precedes models;
  no proxy, no imputation, no panel-specific recovery, no replay).
