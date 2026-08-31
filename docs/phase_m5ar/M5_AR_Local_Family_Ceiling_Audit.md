# M5-AR Local-Family Ceiling Audit

## Status: NOT STARTED

AR0 was not run because the PF3 parent-freeze gate failed first.  The stored
PF1/PF2/PF3 `VRF` values are derived from evaluations whose event indicator
uses `label != "NOMINAL"`, although the frozen benchmark's nominal label is
`S0`.  They therefore cannot be treated as scientifically compatible
rare-event VRF records for a local-family upper envelope.

Any provisional ceiling calculated before this mismatch was identified was
deleted and is not a result of record.  There is no valid M5-AR ceiling,
saturation index, diminishing-return ladder, or residual-gap table in this
run.
