"""C0/C-reference: build and stability-check the numerical reference solution."""

from common import REFERENCE_CONFIG, RESULTS_ROOT, run_case, write_json
from hyptraj.simulation.trajectory import SolverConfig


def main() -> None:
    reference = run_case(REFERENCE_CONFIG)
    check_config = SolverConfig(
        method="DOP853",
        rtol=1e-12,
        atol=REFERENCE_CONFIG.atol.copy(),
        max_step=0.05,
        dense_output=True,
    )
    check = run_case(check_config)

    keys = [
        "capture_time_s", "capture_altitude_m", "capture_velocity_mps",
        "rti_time_s", "rti_altitude_m", "rti_velocity_mps", "rti_range_m",
        "ground_time_s", "ground_range_m", "ground_velocity_mps",
    ]
    stability = {k: abs(reference[k] - check[k]) for k in keys}
    payload = {"reference": reference, "reference_check": check, "stability_abs_delta": stability}
    write_json(RESULTS_ROOT / "reference" / "reference.json", payload)

    print("Numerical reference created.")
    print(f"capture = {reference['capture_time_s']:.12f} s")
    print(f"RTI     = {reference['rti_time_s']:.12f} s, R={reference['rti_range_m']/1000:.9f} km")
    print(f"ground  = {reference['ground_time_s']:.12f} s")
    print(f"0.1 -> 0.05 s RTI-time delta = {stability['rti_time_s']:.3e} s")


if __name__ == "__main__":
    main()
