# M3-S25-R1 P_ref Source Audit

Status: **PASS** (2026-09-06T23:09:41+0800); P_ref sampling budget = **0**.

- Registry: `configs/phase_m3s25r1/m3s25r1_p_ref_registry.json`
  (exactly 30 entries:
  {'M3-D2': 8, 'M3-CF1N': 8, 'M3-S2S': 8, 'M3-WCF1': 6}).
- The 8 M3-S2S new configs use the durable COMPLETE parent PREF records
  (`results/phase_m3s2s/pref/`): parent pref ledger shows exactly one
  STARTED + one COMPLETE per unit and COMPLETE.record_file_hash equals
  the file hash.
- All other configs use the byte-verified vendored snapshots under
  `configs/phase_m3s2s/reference_truth_protocol/pref_records/`
  (CF1N / WCF1 / legacy M3-D2).
- Every entry: source exists -> source hash verified -> protocol
  compatible (governing pref protocol snapshot
  `91ff5dd8898936cc...`) -> exactly
  one durable source.  Any failure => M3-S25-R1-X / STOP / NO P_ref
  RESAMPLING.
