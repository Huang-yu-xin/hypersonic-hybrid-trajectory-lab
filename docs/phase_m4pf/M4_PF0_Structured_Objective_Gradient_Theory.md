# M4-PF0 Structured Objective-Gradient Theory

## 1. Scope

This document derives the covariance objective gradient used by M4-PF. It is a
continuation of the frozen M3 scalar second-moment gradient, not a descriptive
covariance-matching rule. PF0 uses no trajectory simulation.

## 2. Objective and mixture proposal

Let the rare-event second moment under proposal `q` be

\[
M_2(q)=\int_A \frac{p(x)^2}{q(x)}\,dx.
\]

For a mixture

\[
q(x)=\sum_j\pi_jq_j(x),
\qquad
r_k(x)=\frac{\pi_kq_k(x)}{q(x)},
\]

define the normalized variance-mass measure

\[
d\nu_V(x)=\frac{1_A(x)p(x)^2/q(x)}{M_2(q)}\,dx.
\]

Only component `k` is perturbed; mixture weights, component means and all
other covariances remain fixed.

## 3. Symmetric log-covariance perturbation

For `B=B^T`, perturb

\[
\Sigma_k(\epsilon)=\Sigma_k^{1/2}
\exp(\epsilon B)\Sigma_k^{1/2}.
\]

At zero, with

\[
z_k=\Sigma_k^{-1/2}(x-\mu_k),
\]

the Gaussian component score is

\[
\left.\partial_\epsilon\log q_k(x;\epsilon)\right|_0
=\frac12\left(z_k^TBz_k-\operatorname{tr}B\right).
\]

Because only component `k` changes,

\[
\partial_\epsilon\log q(x)=r_k(x)\,
\partial_\epsilon\log q_k(x).
\]

Differentiating the reciprocal proposal density in `M2` gives

\[
\begin{aligned}
g_{k,B}
&=\left.\partial_\epsilon M_2(q_\epsilon)\right|_0\\
&=-\int_A\frac{p(x)^2}{q(x)}
\left.\partial_\epsilon\log q(x)\right|_0dx\\
&=\frac{M_2}{2}E_{\nu_V}\left[
r_k\{\operatorname{tr}B-z_k^TBz_k\}\right].
\end{aligned}
\]

Using `z^T B z=<zz^T,B>_F`, the symmetric matrix representation is

\[
\boxed{
G_k=\frac{M_2}{2}E_{\nu_V}
\left[r_k(I-z_kz_k^T)\right]
}
\]

and

\[
\boxed{g_{k,B}=\langle G_k,B\rangle_F.}
\]

## 4. Exact scalar recovery

M3 parameterizes the isotropic covariance by

\[
\Sigma_k=s_k^2I,
\qquad \theta_k=\log s_k^2.
\]

An increment in `theta` is exactly the log-covariance direction `B=I`, so

\[
g_{scalar}=g_{k,I}=\operatorname{tr}G_k.
\]

Substitution gives

\[
\operatorname{tr}G_k
=\frac{M_2}{2}E_{\nu_V}\left[
r_k(d-\|z_k\|^2)\right].
\]

For `Sigma=s^2 I`, `||z||^2=||x-mu||^2/s^2`, which is exactly the frozen M3
formula. There is no additional factor of two: the scalar parameter is
`log(s^2)`, not `log(s)`.

The finite-sample implementation uses the same M3 variance-mass normalization:

\[
\widehat M_2=\frac1N\sum_i a_i,
\qquad \bar a_i=\frac{a_i}{\sum_j a_j},
\]

\[
\widehat G_k=\frac{\widehat M_2}{2}
\sum_i\bar a_i\widehat r_{ki}(I-z_{ki}z_{ki}^T).
\]

Taking its trace is algebraically identical to the existing
`scalar_gradient_estimate` output.

## 5. Rank-1 and rank-2 structure

For a unit vector `v` and `B=vv^T`,

\[
g_{k,v}=v^TG_kv
=\frac{M_2}{2}E_{\nu_V}
\left[r_k\{1-(v^Tz_k)^2\}\right].
\]

Thus a negative eigenvalue indicates that gradient descent widens along its
eigenvector; a positive eigenvalue indicates shrinkage. Mixed positive and
negative eigenvalues can cancel in the scalar trace even while the full matrix
gradient is strong.

For `G=U Lambda U^T`, PF1 candidates use eigenpairs ordered by descending
absolute eigenvalue:

\[
\widetilde G_r=\sum_{i=1}^r\lambda_{(i)}v_{(i)}v_{(i)}^T,
\qquad r\in\{1,2\}.
\]

## 6. SPD update semantics

The structured descent update is

\[
\Sigma'_k=\Sigma_k^{1/2}
\exp(-\eta\widetilde G_r)\Sigma_k^{1/2}.
\]

For symmetric `G`, the exponential is strictly positive definite. Congruence
with the SPD square root therefore preserves SPD for every finite step. The
implementation symmetrizes inputs, uses `eigh`, optionally normalizes by the
Frobenius norm, clips pre-registered log-step eigenvalues, and rejects updates
that exceed a pre-registered condition-number ceiling.

The additive update `Sigma-eta G` is not used because it has no general SPD
guarantee.

## 7. Spectral diagnostics

For eigenvalues ordered by absolute magnitude, PF0 defines

\[
R_1=\frac{|\lambda_{(1)}|}{\sum_i|\lambda_i|},
\qquad
R_2=\frac{|\lambda_{(1)}|+|\lambda_{(2)}|}
{\sum_i|\lambda_i|},
\]

\[
C=1-\frac{|\sum_i\lambda_i|}{\sum_i|\lambda_i|+\epsilon},
\]

and

\[
A=\frac{\|G\|_F}{|\operatorname{tr}G|/\sqrt d+\epsilon}.
\]

`C` is clipped to `[0,1]`; a zero matrix receives `C=0`. Large `A` or `C`
would indicate structure hidden by the scalar trace, but neither is interpreted
causally without an intervention experiment.

## 8. Deterministic Gaussian validation

For the mathematical fixture, let target `p=N(0,T)`, proposal `q=N(0,S)` and
event region be all of `R^d`. When

\[
2T^{-1}-S^{-1}\succ0,
\]

the second moment is

\[
M_2=|T|^{-1}|S|^{1/2}
|2T^{-1}-S^{-1}|^{-1/2}.
\]

The normalized variance-mass distribution is Gaussian with covariance

\[
V=(2T^{-1}-S^{-1})^{-1},
\]

so the exact log-covariance gradient is

\[
G=\frac{M_2}{2}
\left[I-S^{-1/2}VS^{-1/2}\right].
\]

Central differences of the closed-form `M2` under
`S^(1/2) exp(epsilon B) S^(1/2)` converge quadratically to `<G,B>`. The PF0
fixture checks identity, rank-1 and mixed symmetric directions without random
sampling or a trajectory simulator; at `epsilon=1e-4` its maximum relative
error is approximately `1.51e-7`.

## 9. Limitations

The formulas identify what could be reconstructed from persisted sample-level
pilot data. Existing frozen result JSONs retain aggregate scalar gradients,
ESS, M2 and decisions, but not the sample coordinates, variance-mass inputs,
responsibilities and strata required to form the matrix scatter term.
Consequently PF0 cannot produce real-state eigenspectra without new data.

This limitation does not weaken scalar M3 or imply directional structure is
present. It means only that the hypothesis is not identifiable from the
current persisted artifacts. Any new data generation belongs to a separately
locked PF1 protocol.
