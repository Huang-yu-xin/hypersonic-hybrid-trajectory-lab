# M3-S2S Human Approval

Three independent authorization gates (taskbook Sec. 2).  Codex must not
change any NO to YES.

TRUTH_SAMPLING_AUTHORIZED: NO
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO
AUTHORIZER: (awaiting explicit gate-by-gate human authorization)
AUTHORIZATION_DATE: (not yet granted)

Gate semantics: T1 flow -- first authorize TRUTH_SAMPLING only; after the
truth panel freeze (30/30/30/30 or M3-S2S-PANEL-BLOCKED) STOP for re-audit;
then ARM_A; ARM_B only after a valid M3-S2S-B-GATE plus an explicit
ARM_B_AUTHORIZED: YES commit.  Scope, failure rules, and budget ceilings are
frozen in the contracts; any durable-persistence failure after sampling
starts => M3-S2S-X => STOP => NO REPLAY.
