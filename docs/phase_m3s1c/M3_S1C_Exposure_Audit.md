# M3-S1C Exposure Audit

Status: **PASS** (live, 2026-09-06T09:55:59+0800); per-state bitsets in
`results/phase_m3s1c/preflight/m3s1c_exposure_audit_rows.csv`.

Eight preregistered exposure bits per candidate (any 1 => ineligible => STOP):
PI1VNR development panel; PI1VN partial run; PI1V Attempt-2; gradient pilot;
V1 probe; S1 threshold search; S1 diagnostics (LOSO/LOCO); previous
confirmations.

## Bit 8 formal semantics (AMENDMENT B)

`previous_confirmation_exposure` = previous **controller/comparator/policy-level**
confirmation exposure, classified by RECORD CONTENT with nearest-ancestor
namespace inheritance — never by filename:

- comparator fields (g_hat / CI / gradient_valid / S1 / V1 / r_hat /
  selected_action / deployment / action_sign / ESS_grad / ...) or a
  comparator-pattern namespace (GRAD|PROBE|TRIAL|V1|S1|POLICY) => FORBIDDEN;
- truth/reference fields (confirmed_label / provisional_label / P_ref_hash /
  p_ref_hash) or a truth-stream namespace (...-REF / ...-CONFIRM) with no
  comparator field => ALLOWED (the frozen truth stratum the panel requires);
- UNKNOWN candidate-bearing record => UNRESOLVED => STOP panel freeze
  (never auto-allowed); unresolved records at this audit = 0.

Without this distinction the confirmation design is self-contradictory: the
panel requires frozen W/S/HOLD/AMBIGUOUS truth, but the high-budget reference
characterization that establishes that truth would itself disqualify every
state.

- Candidates scanned = 42; any_exposed = False.
