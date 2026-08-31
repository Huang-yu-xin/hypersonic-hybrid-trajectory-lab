# M5-AR Event / Topology Representation Audit

## Status: NOT STARTED

The live parent audit established only the upstream semantic mismatch needed
to trigger the hard stop:

- frozen nominal label: `S0`;
- downstream comparison literal: `NOMINAL`;
- affected pipeline: M3-D, M3-BV2/M3 scalar, PF1, PF2 and PF3;
- PF3 A1 stored probability median: approximately `1.00008`;
- frozen event probability median: approximately `0.07478`.

This is a parent-evidence validity defect, not an M5-AR R3 finding.  AR1 did
not assess representation compression or authorize an event-representation
route.  M5-AR also did not define a new event predicate; the audit replayed
the frozen `BenchmarkConfig.label` implementation.
