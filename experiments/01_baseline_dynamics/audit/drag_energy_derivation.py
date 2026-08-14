"""Phase B.5-B3-B (EXPLORATORY): drag-energy / terminal-interface derivation.

Lightweight derivation + feasibility sandbox ONLY.  No controller tuning,
no optimization, no production implementation.

Contents
--------
1. Energy-state derivation and numerical verification of
        dE/dt = -D v / m        (E = v^2/2 - mu/r,  mu = g0 Re^2)
   on the QEG + post-QEG trajectories.
2. Energy-parameterized dynamics:
        dh/dE, dtheta/dE, dgamma/dE = (dx/dt) / (dE/dt)
   verified numerically; singular regimes (D -> 0, v -> 0) identified.
3. Reachable post-QEG corridor: constant-u_L probes
        u_L in {0, 0.25, 0.5, 0.75, 1.0}
   from the identical QEG-end state, mapped in D-E, h-v, q-v space
   (T1 = u_L=1, T2 = u_L=0 are the envelope extremes).
4. Control-authority finding: at a fixed state, a_D = D/m and
   da_D/dt are state-determined (u_L-independent); u_L shapes the
   FUTURE a_D path only through gamma_dot (indirect, path-level control).

Outputs (results/audit/phase_b5/):
    drag_energy_derivation.json
    fig_b3b_D_E_corridor.png, fig_b3b_h_v_corridor.png, fig_b3b_q_v.png,
    fig_b3b_dEdt_verify.png
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

PROJECT_ROOT = Path(__file__).resolve().parents[3]

import qeg_capture_exploration as qeg  # noqa: E402
from hyptraj.models.dynamics import atmospheric_dynamics, derived_quantities  # noqa: E402
from hyptraj.models.gravity import gravity_acceleration  # noqa: E402
from hyptraj.simulation.events import make_ground_event  # noqa: E402

AUDIT_DIR = qeg.AUDIT_DIR

MU = 9.81 * 6_371_000.0**2  # mu = g0 Re^2 [m^3/s^2]


def specific_energy(state):
    """E = v^2/2 - mu/r  [J/kg] (exact for the spherical nonrotating model)."""
    r, _th, v, _ga = state
    return v * v / 2.0 - MU / r


def energy_altitude(state, g0=9.81):
    """e = h + v^2/(2 g0) [m]: literature energy altitude (approx form)."""
    r, _th, v, _ga = state
    return (r - 6_371_000.0) + v * v / (2.0 * g0)


def _rhs_const_u(t, y, env, vehicle, control, u):
    """Eq.(4) with fixed u_L = u (0 <= u <= 1)."""
    r, theta, v, gamma = y
    altitude = r - env.earth_radius
    h_eval = max(altitude, 0.0)
    g = gravity_acceleration(h_eval, env)
    rho = env.density_sea_level * np.exp(-h_eval / env.scale_height)
    K = control(t, y)
    q = 0.5 * rho * v * v
    cd = vehicle.drag_coefficient
    drag = q * vehicle.reference_area * cd
    lift = q * vehicle.reference_area * K * cd

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -drag / vehicle.mass - g * np.sin(gamma)
    gamma_dot = (u * lift / (vehicle.mass * v)
                 + (v / r - g / v) * np.cos(gamma))
    return np.array([r_dot, theta_dot, v_dot, gamma_dot])


def main() -> None:
    env, vehicle, initial, control = qeg.cfg.get_baseline_setup()

    # ---- common Entry + QEG to obtain the QEG-end state (identical) -------
    sol1 = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (0.0, 5000.0), qeg._state0(env, initial),
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[qeg._make_gamma0_capture_event()],
    )
    t_capture = float(sol1.t_events[0][0])
    sol2 = solve_ivp(
        lambda t, y: qeg._rhs_qeg(t, y, env, vehicle, control),
        (t_capture, 5000.0), sol1.sol(t_capture),
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[qeg._make_qeg_end_event(env, vehicle, control)],
    )
    t_gate = float(sol2.t_events[0][0])
    x_T = sol2.sol(t_gate).copy()

    # ---- constant-u_L corridor probes from x_T ----------------------------
    ground = make_ground_event(env)
    probes = {}
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        sol = solve_ivp(
            lambda t, y, uu=u: _rhs_const_u(t, y, env, vehicle, control, uu),
            (t_gate, 5000.0), x_T,
            method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
            max_step=10.0, dense_output=True, events=ground,
        )
        tf = float(sol.t_events[0][0])
        t = np.linspace(t_gate, tf, 2001)
        st = sol.sol(t)
        n = len(t)
        h = st[0] - env.earth_radius
        aD = np.empty(n); q = np.empty(n); E = np.empty(n)
        for i in range(n):
            dq = derived_quantities(t[i], st[:, i], env, vehicle, control)
            aD[i] = dq["drag_n"] / vehicle.mass
            q[i] = dq["dynamic_pressure_pa"]
            E[i] = specific_energy(st[:, i])
        probes[u] = {
            "tf_s": tf,
            "t": t, "h_m": h, "v": st[2], "gamma": st[3],
            "aD": aD, "q_pa": q, "E": E,
        }

    # ---- dE/dt exact-identity verification --------------------------------
    # use the u=1 probe (T1 terminal) plus the QEG segment
    tg = np.linspace(t_capture, t_gate, 801)
    sg = sol2.sol(tg)
    n = len(tg)
    hg = sg[0] - env.earth_radius
    Eg = np.empty(n); aDg = np.empty(n)
    for i in range(n):
        dq = derived_quantities(tg[i], sg[:, i], env, vehicle, control)
        aDg[i] = dq["drag_n"] / vehicle.mass
        Eg[i] = specific_energy(sg[:, i])

    dE_dt_numeric = np.gradient(Eg, tg)
    dE_dt_formula = -aDg * sg[2]
    rel_err = np.abs(dE_dt_numeric - dE_dt_formula) / np.maximum(
        np.abs(dE_dt_formula), 1e-9)

    # also on the T1 terminal probe
    p1 = probes[1.0]
    n1 = len(p1["t"])
    dE1_num = np.gradient(p1["E"], p1["t"])
    dE1_form = -p1["aD"] * p1["v"]
    rel_err1 = np.abs(dE1_num - dE1_form) / np.maximum(np.abs(dE1_form), 1e-9)

    # ---- energy-parameterized derivatives (numeric vs analytic) -----------
    def analytic_dh_dE(st, aD):
        _r, _th, v, ga = st
        return -np.sin(ga) / aD  # (v sin g)/( -aD v ) ... = -sin(g)/aD

    def analytic_dth_dE(st, aD, r):
        _r, _th, v, ga = st
        return -np.cos(ga) / (aD * r)

    def analytic_dga_dE(st, aD, u, control, env, vehicle):
        r, _th, v, ga = st
        g = gravity_acceleration(r - env.earth_radius, env)
        dq = derived_quantities(0.0, st, env, vehicle, control)
        L = dq["lift_n"]
        # d(gamma)/dE = gamma_dot / (dE/dt)
        #             = -u*L/(m*aD*v^2) - (cos(gamma)/aD)*(1/r - g/v^2)
        return -(u * L / (vehicle.mass * aD * v * v)
                 + (np.cos(ga) / aD) * (1.0 / r - g / (v * v)))

    # rebuild the u=0 and u=1 probes with full state arrays (theta needed)
    probes2 = {}
    for u in (0.0, 1.0):
        sol = solve_ivp(
            lambda t, y, uu=u: _rhs_const_u(t, y, env, vehicle, control, uu),
            (t_gate, 5000.0), x_T,
            method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
            max_step=10.0, dense_output=True, events=ground,
        )
        tf = float(sol.t_events[0][0])
        t = np.linspace(t_gate, tf, 2001)
        st = sol.sol(t)
        probes2[u] = {"t": t, "st": st}

    energy_derivs = {}
    for u_name, (u, rec) in [("T1_u1", (1.0, probes2[1.0])),
                             ("T2_u0", (0.0, probes2[0.0]))]:
        t = rec["t"]; st = rec["st"]
        n = len(t)
        aD = np.empty(n); E = np.empty(n)
        for i in range(n):
            aD[i] = derived_quantities(t[i], st[:, i], env, vehicle, control)["drag_n"] / vehicle.mass
            E[i] = specific_energy(st[:, i])
        dh = np.gradient(st[0], t) / np.gradient(E, t)
        dth = np.gradient(st[1], t) / np.gradient(E, t)
        dga = np.gradient(st[3], t) / np.gradient(E, t)
        dh_a = np.array([analytic_dh_dE(st[:, i], aD[i]) for i in range(n)])
        dth_a = np.array([analytic_dth_dE(st[:, i], aD[i], st[0, i]) for i in range(n)])
        dga_a = np.array([analytic_dga_dE(st[:, i], aD[i], u, control, env, vehicle)
                          for i in range(n)])
        # relative error is meaningless where the true value crosses zero;
        # report both max absolute and max relative (with a floor)
        def err_stats(num, ana):
            abs_err = np.abs(num - ana)
            scale = np.max(np.abs(ana))
            mask = np.abs(ana) > 1e-9 * scale
            rel = np.abs(num - ana)[mask] / np.abs(ana)[mask]
            return float(np.max(abs_err)), float(np.max(rel) if len(rel) else 0.0)

        e_h = err_stats(dh, dh_a)
        e_th = err_stats(dth, dth_a)
        e_ga = err_stats(dga, dga_a)
        energy_derivs[u_name] = {
            "dh_dE_max_abs_err": e_h[0],
            "dh_dE_max_rel_err": e_h[1],
            "dtheta_dE_max_abs_err": e_th[0],
            "dtheta_dE_max_rel_err": e_th[1],
            "dgamma_dE_max_abs_err": e_ga[0],
            "dgamma_dE_max_rel_err": e_ga[1],
        }

    # ---- corridor characterization ----------------------------------------
    # common E grid over the post-gate interval: [gate E, lowest final E]
    E_max = probes[1.0]["E"][0]  # gate energy (same for all probes)
    E_min = min(p["E"][-1] for p in probes.values())
    E_grid = np.linspace(E_max, E_min, 200)
    # for each probe, interpolate aD(E), h(E), q(E)
    corridor = {"E_grid": E_grid.tolist()}
    aD_env = np.full_like(E_grid, np.nan)
    h_env_lo = np.full_like(E_grid, np.nan)
    h_env_hi = np.full_like(E_grid, np.nan)
    q_env_lo = np.full_like(E_grid, np.nan)
    q_env_hi = np.full_like(E_grid, np.nan)
    for i, Ee in enumerate(E_grid):
        vals_aD = [np.interp(Ee, p["E"][::-1], p["aD"][::-1]) for p in probes.values()]
        vals_h = [np.interp(Ee, p["E"][::-1], p["h_m"][::-1]) for p in probes.values()]
        vals_q = [np.interp(Ee, p["E"][::-1], p["q_pa"][::-1]) for p in probes.values()]
        aD_env[i] = max(vals_aD) - min(vals_aD)
        h_env_lo[i], h_env_hi[i] = min(vals_h), max(vals_h)
        q_env_lo[i], q_env_hi[i] = min(vals_q), max(vals_q)
    corridor["aD_envelope_width_mps2"] = aD_env.tolist()
    corridor["h_envelope_lo_m"] = h_env_lo.tolist()
    corridor["h_envelope_hi_m"] = h_env_hi.tolist()
    corridor["q_envelope_lo_pa"] = q_env_lo.tolist()
    corridor["q_envelope_hi_pa"] = q_env_hi.tolist()

    # instantaneous drag authority at the gate (state-determined)
    dq_gate = derived_quantities(t_gate, x_T, env, vehicle, control)
    g_gate = gravity_acceleration(x_T[0] - env.earth_radius, env)
    aD_gate = dq_gate["drag_n"] / vehicle.mass
    v_gate = x_T[2]; gam_gate = x_T[3]
    # da_D/dt = aD * [ -sin(g)(v/H + 2g/v) - 2 aD / v ]  (state-determined)
    daD_dt_gate = aD_gate * (-np.sin(gam_gate) * (v_gate / env.scale_height + 2 * g_gate / v_gate)
                             - 2 * aD_gate / v_gate)

    report = {
        "common_qeg_end_state": {
            "t_s": t_gate, "h_km": (x_T[0] - env.earth_radius) / 1000.0,
            "v_mps": float(v_gate), "range_km": env.earth_radius * x_T[1] / 1000.0,
            "E_J_per_kg": float(specific_energy(x_T)),
            "energy_altitude_km": float(energy_altitude(x_T) / 1000.0),
            "a_D_mps2": float(aD_gate),
            "da_D_dt_mps3": float(daD_dt_gate),
        },
        "dE_dt_verification": {
            "exact_identity": "dE/dt = -D v / m  (derived: g = mu/r^2 cancels the gravity term)",
            "max_rel_err_QEG_segment": float(np.max(rel_err)),
            "max_rel_err_T1_terminal": float(np.max(rel_err1)),
        },
        "energy_parameterized_derivatives": energy_derivs,
        "corridor_probes": {
            str(u): {"tf_s": p["tf_s"],
                     "aD_range_mps2": [float(p["aD"][0]), float(p["aD"][-1])],
                     "v_f_mps": float(p["v"][-1]),
                     "q_max_pa": float(np.max(p["q_pa"]))}
            for u, p in probes.items()
        },
        "corridor": corridor,
        "control_authority_finding": (
            "At a fixed state a_D and da_D/dt are state-determined "
            "(u_L-independent); u_L shapes the FUTURE drag path only via "
            "gamma_dot (indirect path-level control, same architecture as "
            "Shuttle drag-control entry guidance)."
        ),
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "drag_energy_derivation.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    # ---- console -----------------------------------------------------------
    print("=== Phase B.5-B3-B drag-energy derivation (exploratory) ===")
    print(f"QEG-end: t={t_gate:.3f}s h={(x_T[0]-env.earth_radius)/1000:.3f}km "
          f"v={v_gate:.3f} m/s  E={specific_energy(x_T):.1f} J/kg  "
          f"a_D={aD_gate:.4f} m/s^2  da_D/dt={daD_dt_gate:.5f} m/s^3")
    print(f"\ndE/dt = -D v / m: max rel err on QEG = {np.max(rel_err):.3e}, "
          f"on T1 terminal = {np.max(rel_err1):.3e}  (exact identity)")
    print("\nEnergy-parameterized derivatives (numeric vs analytic, max rel err):")
    for k, v in energy_derivs.items():
        print(f"  {k}: {v}")
    print("\nCorridor probes (constant u_L from the gate state):")
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = probes[u]
        print(f"  u_L={u:.2f}: tf={p['tf_s']:8.1f}s  aD range "
              f"[{p['aD'][0]:.2f}, {p['aD'][-1]:.2f}] m/s^2  "
              f"v_f={p['v'][-1]:6.1f} m/s  q_max={np.max(p['q_pa'])/1000:.1f} kPa")
    print(f"\ncorridor in D-E: envelope width [m/s^2] from "
          f"{np.nanmin(aD_env):.2f} to {np.nanmax(aD_env):.2f} over the common E range")

    # ---- figures -----------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cmap = {0.0: "tab:purple", 0.25: "tab:olive", 0.5: "tab:cyan",
            0.75: "tab:orange", 1.0: "tab:blue"}

    # D-E corridor
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for u, p in probes.items():
        lab = "T2 u_L=0" if u == 0.0 else ("T1 u_L=1" if u == 1.0 else f"u_L={u:.2f}")
        ax.plot(p["E"], p["aD"], lw=1.1, color=cmap[u], label=lab)
    # QEG equilibrium drag (aD_eq = (g - v^2/r)/K with gamma~0) on the same E axis
    # (the QEG segment itself is the equilibrium-following reference)
    ax.plot(Eg, aDg, lw=1.6, color="tab:green", label="QEG segment (equilibrium-following)")
    ax.set_xlabel("Specific energy E = v^2/2 - mu/r [J/kg]")
    ax.set_ylabel("Drag acceleration a_D = D/m [m/s^2]")
    ax.set_title("B.5-B3-B: post-QEG reachable corridor in D-E")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_b3b_D_E_corridor.png", dpi=300); plt.close(fig)

    # h-v corridor
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for u, p in probes.items():
        lab = "T2 u_L=0" if u == 0.0 else ("T1 u_L=1" if u == 1.0 else f"u_L={u:.2f}")
        ax.plot(p["v"] / 1000.0, p["h_m"] / 1000.0, lw=1.1, color=cmap[u], label=lab)
    ax.set_xlabel("Velocity [km/s]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("B.5-B3-B: post-QEG reachable corridor in h-v")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_b3b_h_v_corridor.png", dpi=300); plt.close(fig)

    # q-v corridor
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for u, p in probes.items():
        lab = "T2 u_L=0" if u == 0.0 else ("T1 u_L=1" if u == 1.0 else f"u_L={u:.2f}")
        ax.plot(p["v"] / 1000.0, p["q_pa"] / 1000.0, lw=1.1, color=cmap[u], label=lab)
    ax.set_xlabel("Velocity [km/s]"); ax.set_ylabel("Dynamic pressure [kPa]")
    ax.set_title("B.5-B3-B: post-QEG reachable corridor in q-v")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_b3b_q_v.png", dpi=300); plt.close(fig)

    # dE/dt verification plot
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(tg, dE_dt_formula, lw=1.1, color="tab:blue", label="formula: -D v / m")
    ax.plot(tg, dE_dt_numeric, lw=1.1, ls="--", color="tab:red", label="numeric gradient")
    ax.set_xlabel("Time [s] (QEG segment)"); ax.set_ylabel("dE/dt [W/kg]")
    ax.set_title("B.5-B3-B: dE/dt = -D v / m verification")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_b3b_dEdt_verify.png", dpi=300); plt.close(fig)

    print(f"\nreport + 4 figures written to {AUDIT_DIR}")


if __name__ == "__main__":
    main()
