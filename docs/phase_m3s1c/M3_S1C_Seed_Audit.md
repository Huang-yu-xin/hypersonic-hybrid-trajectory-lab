# M3-S1C Seed Audit

Status: **PASS** (live, 2026-09-06T09:56:00+0800).

- Namespace `M3-S1C-GRAD`; 192 planned = 24 states x 8 replicates;
  192 unique; 0 collisions against the live historical
  pool (1112 seeds: all `results/` CSVs with a `seed` column,
  retired PI1VN seed manifest, PI1VNR planned gradient+probe seeds).
- Seeds derived deterministically as sha256(namespace|state_id|rep); frozen
  before the first simulator call in `configs/phase_m3s1c/m3s1c_seeds.json`
  (sha256 d98ff18d24d48c624845dba3958247013f7933818ecdf69039b0a211e50122c8).
