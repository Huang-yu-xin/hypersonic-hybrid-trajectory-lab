# ER-1 Event-Semantics Contract

## Frozen source of truth

The authoritative event predicate is
`hyptraj.m1d.benchmark_family.BenchmarkConfig.label`.  It accepts a static
two-dimensional latent sample `z` and returns one topology label from
`S0, S1, S2, S3, S4`.  `S0` is the nominal complement.  The rare event is
defined exactly as `topology_label != S0`.  This is a static latent-state
classification, not an endpoint-time, trajectory-history or hybrid-switch
predicate.  ER-1 does not introduce a new event definition.

## Namespace contract

| Name/literal | Semantic type | Allowed values | Source of truth | Used by stages |
|---|---|---|---|---|
| `event_indicator` | boolean rare-event membership | `False`, `True` | `event_indicator_from_topology` applied to the frozen predicate | repaired estimators |
| `topology_label` | categorical event topology | `S0`–`S4` | `BenchmarkConfig.label` | M1-D onward |
| `source_stratum` | sampling-design provenance | integer stratum identifiers | the sampler that emitted the sample | stratified pilots/evaluations |
| `proposal_arm` | proposal/controller alternative | stage-specific arm names | each frozen stage protocol | M3 onward |
| nominal topology | topology category | `S0` | `hyptraj.m1d.metrics.NOMINAL` and benchmark family | event predicate |
| nominal proposal arm | proposal alternative | stage-specific, sometimes `base`/`S0`/`P00`/`A0` | stage protocol | arm comparison only |
| `NOMINAL` literal | legacy prose-like string, not a valid topology value in this benchmark | none in estimator logic | no authoritative source | contaminated M3/PF paths |
| `S0` literal | topology label; separately, some summaries also use `S0` as a scalar proposal-family arm | topology `S0` or explicitly typed proposal arm `S0` | topology oracle / PF1 protocol | topology and PF1 arm namespace |

`S0` is a **SEMANTIC COLLISION** in legacy text because it can name the
nominal topology or a PF1 proposal arm.  Repaired code must carry the domain
explicitly and must never derive event membership from proposal-arm or
source-stratum values.

## Estimator contract

For sample `i`, with authoritative boolean event membership `I_i` and
likelihood ratio `L_i = p(X_i)/q(X_i)`:

```text
Z_i = I_i L_i
P_hat = mean(Z_i)
M2_hat = mean(Z_i^2)
variance_mass_i = Z_i^2
```

For pooled fixed-mixture pilots whose sampling density is `r`, the stored
gradient mass is the equivalent importance contribution
`I_i p(X_i)^2 / (q(X_i) r(X_i))` used by the repository's frozen gradient
identity.  It must still be exactly zero whenever `I_i` is false.  A field
named `variance_mass` is not valid merely by name; it must be checked against
the stage-specific formula.

## Domain-separation rules

- Changing `proposal_arm` cannot change `event_indicator`.
- Changing `source_stratum` cannot change `event_indicator`.
- `proposal_arm == topology_label` is forbidden without an explicit adapter.
- The legacy nominal literal must be validated against the predicate's
  declared nominal label; ambiguity raises instead of guessing.
- Corrected artifacts use `event_semantics_schema_version = 2` and record the
  event predicate, estimator formulas, source artifact hash and repair commit.
