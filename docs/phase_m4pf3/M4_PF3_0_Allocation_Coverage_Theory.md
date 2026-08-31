# M4-PF3-0 Allocation and Coverage Theory Lock

## Mixture allocation derivative

For `q=sum_k alpha_k q_k` with `alpha=softmax(beta)`, component
responsibility `r_k=alpha_k q_k/q`, and the normalized second-moment tilted
measure `nu_V`,

\[
\frac{\partial M_2}{\partial\beta_k}
=M_2\left(\alpha_k-\bar r_k\right),\qquad
\bar r_k=E_{\nu_V}[r_k].
\]

Thus `d_beta = r_bar - alpha` is a logit-space descent direction and sums to
zero. PF3-0 reports

\[
A_{alloc}=\tfrac12\sum_k|\bar r_k-\alpha_k|,
\quad R_k=\bar r_k/(\alpha_k+\epsilon),
\]

together with nominal and tilted allocation entropy and effective component
count.

## Tilted coverage

For every persisted sample,

\[
d_{min}^2(x)=\min_k
\|\Sigma_k^{-1/2}(x-\mu_k)\|^2.
\]

The fixed reference thresholds are `chi2.ppf(0.99,d)` and
`chi2.ppf(0.999,d)`. Raw sample fractions and normalized variance-mass
fractions above both thresholds are kept separate. PF3-0 also measures the
uncovered contribution within the samples carrying the largest 1% and 0.1%
of individual variance mass.

## Component-birth derivative

For `q_epsilon=(1-epsilon)q+epsilon g`,

\[
\left.\frac{dM_2(q_\epsilon)}{d\epsilon}\right|_0
=M_2\left(1-E_{\nu_V}[g/q]\right).
\]

The birth score is

\[
S_{birth}(g)=E_{\nu_V}[g/q]-1.
\]

Geometry may only generate a candidate centre. Candidate covariance is copied
unchanged from the nearest existing component; uncovered-sample covariance is
never fitted. A confirmatory birth is admissible only when the pooled score is
positive and the frozen four-stream one-sided 95% Student-t lower confidence
bound is also positive.

## Anchor firewall

The archived PF2 arrays were generated at the S0-selected scalar proposal and
are valid for PF3-0 diagnosis only. PF2 P11 is the preferred intervention
anchor. Every P11 allocation or birth intervention requires fresh P11
construction samples unless an exact reweighting derivation is separately
frozen and tested; no such reweighting is assumed here.

## Routing lock

- Allocation is material when median `A_alloc >= 0.10` or at least 8 of 24
  states have `A_alloc >= 0.15`.
- Coverage is material when median `U99 >= 0.10` or at least 8 of 24 states
  have `U99 >= 0.20`.
- Coverage is severe when any state has `U999 >= 0.25` or any state's top-1%
  variance-mass subset has uncovered contribution at least `0.25`.
- Both material mechanisms route to C; allocation alone routes to A; coverage
  alone routes to B; neither routes to D.

Threshold sensitivity at `0.5x`, `1.0x` and `1.5x` is descriptive only and
cannot replace the primary routing decision.

