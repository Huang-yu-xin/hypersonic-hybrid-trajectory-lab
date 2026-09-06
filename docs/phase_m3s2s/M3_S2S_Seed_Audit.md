# M3-S2S Seed Audit

Status: **PASS** (2026-09-06T12:24:43+0800).

- Arm-A namespace `M3-S2S-A-GRAD`: 1920-seed candidate pool
  (264 states x 8 replicates), 1920 unique, 0 historical
  collisions (all results CSVs + retired PI1VN manifest + PI1VNR planned
  streams + cross-namespace probes); the 960 Arm-A seeds are the frozen
  subset for the selected panel.
- Arm-B namespace `M3-S2S-B-GRAD` frozen and disjoint (delta-tagged
  derivation); truth namespaces reuse the canonical M3-CF1N-* streams with
  new state ids (no collision by construction, verified against history).
