# M3-S2S Human Approval

Three independent authorization gates (taskbook Sec. 2).  Codex must not
change any NO to YES.

## T1 authorization record (TRUTH stage)

- Independent live Git audit of the final runtime-integrity HEAD passed
  (all six execution-readiness items verified; blocker fix at ab5c787
  confirmed; frozen state moved to the current HEAD after the mechanical
  fix commit).
- Explicit human authorization received on 2026-09-06: "T1 authorized --
  change TRUTH_SAMPLING_AUTHORIZED to YES and run the truth stage."
- Scope: the frozen truth streams ONLY -- P_ref for the 8 frozen new
  configs (500k/config), discovery for all 240 frozen candidate states
  (3 x 100k), confirmation for all 240 states (3 x 500k);
  confirmation_scope = ALL_240_FRESH_CANDIDATES; early_stop_on_quota =
  false; planned = max = 436,000,000; no top-up; no candidate
  substitution.  After 488/488 durable COMPLETE: truth assignment +
  m3s2s_truth_exposed_inventory + 120-state panel freeze (or
  M3-S2S-PANEL-BLOCKED => STOP), then STOP for post-truth audit.
  ARM_A / ARM_B remain NOT authorized.

TRUTH_SAMPLING_AUTHORIZED: YES
AUTHORIZER: Human
AUTHORIZATION_DATE: 2026-09-06
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO

Gate semantics: T1 flow -- first authorize TRUTH_SAMPLING only; after the
truth panel freeze (30/30/30/30 or M3-S2S-PANEL-BLOCKED) STOP for re-audit;
then ARM_A; ARM_B only after a valid M3-S2S-B-GATE plus an explicit
ARM_B_AUTHORIZED: YES commit.  Scope, failure rules, and budget ceilings are
frozen in the contracts; any durable-persistence failure after sampling
starts => M3-S2S-X => STOP => NO REPLAY.
