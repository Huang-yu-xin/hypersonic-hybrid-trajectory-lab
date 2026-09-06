# M3-S2S Instrumentation Preflight

Status: **PASS** (2026-09-06T13:33:19+0800).

- Estimator source audited (sha256 `ab62a6c24a6f6bd9...`):
  N_BOOTSTRAP = 500; bootstrap =
  fixed-stratified with seed [seed, 424243]; per-sample arrays a_vec/resp/
  sq/strata (n=20000) are the sufficient statistics; aggregate estimator
  unchanged (persistence-only delta).
- `batches = 20` is a configuration constant, NOT 20 independent batch
  gradients (source-verified; taskbook Sec. 13).
- Sidecar schema m3s2s_instr_v1: npz(a_vec, resp, sq,
  strata, bootstrap_g) — lossless; sha256 recorded in the trial record and
  verified BEFORE ledger COMPLETE.
- Bootstrap draws are never independent scientific trials.
- Capacity: 644,000 B/trial (uncompressed basis);
  Arm-A worst case 0.62 GB;
  Arm-A+Arm-B 1.85 GB; disk free
  169.5 GB.
