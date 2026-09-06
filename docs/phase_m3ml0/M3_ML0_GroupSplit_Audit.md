# M3-ML0 Group Split Audit

Status: **PASS** (2026-09-06T10:57:43+0800).

- Scheme: GroupKFold(5) outer + GroupKFold(4) inner, groups = config_id;
  canonical row order (panel, state_id, rep); deterministic, seed 2026.
- Unique configs = 20; train/test config overlap =
  0; states spanning multiple folds =
  0.
