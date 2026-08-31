# M5-AR Architecture & Regime Review — Execution Lock

## Status

`BLOCKED AT PF3 LIVE FREEZE AUDIT`

This local execution lock transcribes the controlling requirements of the
provided M5-AR taskbook.  The parent tag is `RareTopo-M4-PF3-v0` at
`dbe730d4a0cf12de253e2f46384d9abc99d9a60e`.  AR0--AR4 are analysis-only,
must retain all 24 states, and have the hard invariant
`extra_simulator_calls = 0`.

The taskbook's first gate states that an inconsistent PF3 tag/provenance must
stop M5-AR before the local-family ceiling or any routing analysis.  The live
audit found such an inconsistency: the frozen event oracle emits `S0` for the
nominal class, while the M3-D through PF3 pipeline compares labels against the
literal `NOMINAL`.  The stop rule therefore controls this run.

No proposal experiment, budget change, event redefinition, state exclusion,
M3-Q reopening, AR0--AR4 result, routing verdict, figure set, downstream tag,
or simulator call is authorized in this blocked run.

The preregistered AR0--AR4 rules remain recorded in
`configs/phase_m5ar/m5ar_protocol.json` for a future restart after the parent
evidence has been repaired and separately frozen.
