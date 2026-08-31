# M4-PF3-A Weight-Reallocation Preregistration

PF3-0 locked Route A before this protocol was created. The confirmatory family
therefore contains only A0 and A1; no birth proposal is admissible in PF3-A.

For each frozen state, A0 is the exact PF2 P11 proposal. Four new independent
100,000-sample mixed-pilot streams construct all component responsibilities at
A0 and the normalized M2 allocation

\[
\bar r_k=\sum_i\bar a_i r_{ki}.
\]

With `d_beta=r_bar-alpha`, A1 uses the single locked update

\[
\beta'=\beta+0.20\,d_\beta/\|d_\beta\|_2,
\qquad \alpha'=softmax(\beta').
\]

If the direction norm is below `1e-12`, A1 is the identity. Component means
and covariances remain exactly those of A0. There is no statewise step tuning.

Discovery uses two states and disjoint small streams for implementation and
safety only. Confirmation retains all 24 states and uses eight new paired CRN
replicates of 100,000 samples for both arms. A1 receives one new 500,000-sample
probability characterization; A0 reuses the frozen PF2 P11 characterization.

FreeOracle selects the lower median replicate estimator variance per state,
with A0 winning exact ties. Only the selected 100,000-sample arm is charged to
the counterfactual deployable endpoint. Fresh gradients, probability
characterization, discovery and all arm search are reported as audit-only
actual scientific cost.

The primary absolute gates remain median FreeOracle VRF above 1 and above 0.1.
PF3-A is available only if allocation is essential and the first gate passes;
PF3-C applies between the gates, PF3-D at or below 0.1, and PF3-E to any
protocol, anchor, baseline, numerical or accounting invalidity.
