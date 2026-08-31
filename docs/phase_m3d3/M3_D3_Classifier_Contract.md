# M3-D3 classifier contract (verbatim D2 reuse)

D3-0 does not change the D2 classifier. Objective is `M2=mean((I[topology != S0] p/q_arm)^2)`. The three CRN arms are BASE, WIDEN and SHRINK. WIDEN requires its relative M2 reduction below -1%, lower M2 than SHRINK, both base contrasts supported at |delta M2| >= 2 paired SE, and direction margin >=5%. SHRINK is symmetric. HOLD requires neither improvement rule and both arm/base ratios within +/-3%. Unsupported required contrast, failed direction margin, or no unique class is AMBIGUOUS. Probability failure, non-finite arithmetic, illegality, draw mismatch, or ESS<20 is INVALID.

Decision-map coordinates are the native ratios `M2(widen)/M2(base)-1` and `M2(shrink)/M2(base)-1`. `hold_proximity_score=max(abs(r_w),abs(r_s))` is descriptive only and never replaces this contract.
