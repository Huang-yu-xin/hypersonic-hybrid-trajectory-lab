"""M3 -- Second-Moment Gradient Covariance Control (preregistered task
``docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md``).

Modules
-------
covariance_gradient : analytical population theorem + quadrature/FD machinery
gradient_estimator : finite-sample stratified pilot estimator (bootstrap CI)
direction_policy   : WIDEN/SHRINK/HOLD decision rule with preregistered gates
metrics            : paired counterfactual aggregation and gate quantities

Frozen-firewall discipline inherited from M1/M1-D/M2: no benchmark-design
reference data enters any module here.
"""
