# M3-ML0 Feature Leakage Audit

Status: **PASS** (all model feature sets checked against the frozen
forbidden list; 0 hits).

- Model features: B1 ['S1'];
  B2 ['S1', 'g_hat', 'SE_g', 's2', 'curvature_c']; B3 ['S1', 'g_hat', 'abs_g_hat', 'SE_g', 'CI_width', 's2', 'curvature_c', 'ESS_grad', 'gradient_valid'].
- Forbidden (never in X): truth/label, confirmed/provisional labels, P_ref,
  high-budget r_hat/gain, probe outcomes, state_id, config_id (grouping
  only), panel identity, development-vs-confirmation flags.
- F1 availability: ESS_grad included (online, truth-free); p_hat_grad /
  batch dispersion / batch variance NOT persisted in trial records =>
  excluded, never imputed or proxied.
- Invalid-gradient trials (7 of 384): never model
  input; deterministic ABSTAIN in every policy.
