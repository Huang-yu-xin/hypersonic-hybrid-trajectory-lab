# M5-AR Static Mixture Architecture Audit

## Status: NOT STARTED

AR2 was not run.  Stored PF3 `variance_mass` is not valid rare-event tilted
mass under the frozen event predicate.  A direct frozen-oracle replay shows
that true event samples account for only approximately `1.98%` of stored
`variance_mass` at the median state (range approximately `0.73%` to `6.50%`).

Consequently responsibility entropy, coverage, clustering, component
fragmentation and tilted-mass multimodality computed from those arrays cannot
support R1.  No static architecture verdict is issued.
