# M4-PF2 Mean-Gradient Theory and PF2-0 Lock

## 1. Objective-gradient continuity

For the mixture proposal `q=sum_k alpha_k q_k`, define component
responsibility `r_k=alpha_k q_k/q` and the normalized second-moment measure

\[
d\nu_V(x)=\frac{1_A(x)p(x)^2/q(x)}{M_2(q)}dx.
\]

For a Gaussian component,

\[
\nabla_{\mu_k}\log q_k(x)=\Sigma_k^{-1}(x-\mu_k).
\]

Differentiating the reciprocal proposal density gives

\[
\boxed{\nabla_{\mu_k}M_2
=-M_2E_{\nu_V}[r_k\Sigma_k^{-1}(x-\mu_k)].}
\]

With `z_k=Sigma_k^(-1/2)(x-mu_k)` and

\[
a_k=E_{\nu_V}[r_kz_k],
\]

the gradient is

\[
\boxed{\nabla_{\mu_k}M_2=-M_2\Sigma_k^{-1/2}a_k.}
\]

For the whitened perturbation
`mu(epsilon)=mu+epsilon Sigma^(1/2)u`,

\[
\left.\frac{dM_2}{d\epsilon}\right|_0=-M_2a_k^Tu.
\]

Hence `u=+a_k/||a_k||` is a descent direction. The sign is positive for the
mean displacement even though the Euclidean objective gradient carries a
minus sign.

## 2. Finite-sample convention

PF2 uses the frozen M3 variance-mass normalization. For per-sample masses
`a_i`, responsibilities `r_ki` and whitened coordinates `z_ki`,

\[
\widehat a_k=\sum_i\frac{a_i}{\sum_j a_j}r_{ki}z_{ki}.
\]

No descriptive event centroid or covariance enters this estimator.

## 3. Mean step

After the confirmatory protocol is separately frozen, the intended one-step
intervention is

\[
\Delta\mu_k=0.20\,\Sigma_k^{1/2}
\frac{\widehat a_k}{\|\widehat a_k\|}.
\]

The numerical-zero threshold is an implementation tolerance, not a learned
HOLD rule. A vector below that threshold yields the identity mean update.
For every nonzero update,

\[
\|\Sigma_k^{-1/2}\Delta\mu_k\|=0.20.
\]

## 4. Joint first-order semantics

Both the mean vector and PF1 rank-1 covariance matrix gradient must be
estimated at the same locked anchor proposal. P11 uses the anchor covariance
to form the mean displacement and the anchor matrix gradient to form the
matrix-exponential covariance update. The updates are then applied
simultaneously; neither gradient is recomputed inside the one-step proposal.

## 5. Analytic Gaussian validation

For `p=N(m_t,T)` and `q=N(m_q,S)` on all of `R^d`, completing the square in
`p^2/q` gives a Gaussian tilted measure with precision

\[
H=2T^{-1}-S^{-1}
\]

and mean

\[
m_V=H^{-1}(2T^{-1}m_t-S^{-1}m_q).
\]

Thus

\[
a=S^{-1/2}(m_V-m_q).
\]

Central differences under `m_q +/- epsilon S^(1/2)u` match
`-M2 a^T u` for multiple deterministic directions. The same fixture verifies
that the normalized positive `a` direction is locally descending and that a
change of physical units rescales the Euclidean displacement while preserving
its Mahalanobis magnitude.

## 6. PF2-0 boundary

PF2-0 performs no simulator calls. Real-state mean gradients may be reported
only if the frozen PF1 records contain numeric sample arrays and exact proposal
identity. An aggregate matrix gradient is not enough to recover the first
moment. A gradient evaluated at the PF1 base proposal also cannot silently be
treated as a gradient at the S0-selected widen/shrink proposal.

The confirmatory protocol, seeds and complete 2x2 design will be appended only
after the PF2-0 identifiability and anchor-compatibility audit is frozen.

## 7. Confirmatory preregistration

PF2-0 found that the PF1 sample arrays are unavailable and the gradient source
does not match the preferred anchor in any of the 24 states. PF2 therefore
locks fresh gradient construction at the exact per-state S0-selected scalar
anchor. The same four pooled 100k mixed-pilot streams construct both `a_k` and
`G_k`; their cost is audit-only and their sample arrays are persisted for
future provenance.

The mean step is fixed at 0.20 Mahalanobis units with numerical-zero threshold
`1e-12`. The covariance cell reuses the PF1 rank-1 update exactly. P11 forms
both updates from the common anchor and applies them simultaneously.

The primary design contains only P00, P10, P01 and P11 on all 24 frozen
Value-Axis states. Confirmation uses eight new paired 100k replicates per cell,
with CRN shared across the four cells. All PF2 seeds are disjoint from PF1 and
from PF2 discovery.

P00 is proposal-identical to the frozen S0 selected arm. Because the
confirmatory streams are new, its aggregate median VRF must agree with the PF1
anchor within a preregistered 10% relative Monte Carlo tolerance in addition
to passing exact proposal, event, probability and budget identity checks.

For each state, FreeOracle selects the cell with minimum median replicate
estimator variance; exact ties use P00, P10, P01, P11 order. The primary result
is the median statewise selected-cell VRF. Only the selected 100k arm is charged
as deployable; all construction, cell search and unselected evaluations are
reported separately as actual audit-only scientific cost.
