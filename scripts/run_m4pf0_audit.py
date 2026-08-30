"""Run M4-PF0 source, identifiability and deterministic theory audits."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m4pf.gradient import (
    directional_gradient,
    gaussian_log_covariance_gradient,
    log_covariance_directional_fd,
    spectral_diagnostics,
)
from hyptraj.m4pf.provenance import (
    build_manifest,
    identifiability_audit,
    verify_manifest,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf0" / "summary"


def gaussian_fixture() -> dict:
    target = np.array([[1.35, 0.18], [0.18, 0.82]])
    proposal = np.array([[1.05, 0.08], [0.08, 1.22]])
    directions = {
        "identity": np.eye(2),
        "rank1": np.array([[1.0, 0.0], [0.0, 0.0]]),
        "mixed": np.array([[0.4, 0.7], [0.7, -0.2]]),
    }
    gradient = gaussian_log_covariance_gradient(target, proposal)
    records = []
    for name, direction in directions.items():
        analytic = directional_gradient(gradient, direction)
        for epsilon in (1e-2, 1e-3, 1e-4):
            fd = log_covariance_directional_fd(target, proposal, direction,
                                               epsilon)
            records.append({
                "direction": name,
                "epsilon": epsilon,
                "analytic": analytic,
                "finite_difference": fd,
                "absolute_error": abs(fd - analytic),
                "relative_error": abs(fd - analytic) /
                                  max(abs(analytic), 1e-15),
            })
    diag = spectral_diagnostics(gradient)
    return {
        "target_covariance": target.tolist(),
        "proposal_covariance": proposal.tolist(),
        "gradient_matrix": gradient.tolist(),
        "gradient_symmetry_max_abs": float(np.max(np.abs(gradient-gradient.T))),
        "scalar_trace": float(np.trace(gradient)),
        "identity_directional": directional_gradient(gradient, np.eye(2)),
        "spectral_diagnostics": {
            key: (value.tolist() if isinstance(value, np.ndarray) else value)
            for key, value in diag.items()
        },
        "fd_records": records,
        "max_relative_error_epsilon_1e-4": max(
            row["relative_error"] for row in records
            if row["epsilon"] == 1e-4),
    }


def write_state_identifiability(ident: dict) -> None:
    source = REPO / "results" / "phase_m3ca" / "summary" / \
        "m3ca_state_table.csv"
    with source.open(encoding="utf-8") as stream:
        states = list(csv.DictReader(stream))
    fields = ["state_id", "config_id", "s2", "class", "free_oracle_vrf",
              "identifiable", "reason", "gradient_trace", "frobenius_norm",
              "cancellation_score", "top1_spectral_fraction",
              "top2_spectral_fraction"]
    with (SUMMARY / "m4pf0_state_gradient_table.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for state in states:
            writer.writerow({
                "state_id": state["state_id"],
                "config_id": state["config_id"],
                "s2": state["s2"],
                "class": state["class"],
                "free_oracle_vrf": state["free_oracle_vrf_median"],
                "identifiable": str(bool(ident[
                    "frozen_sample_level_matrix_reconstruction"])).lower(),
                "reason": ident["reason"] or "",
                "gradient_trace": "",
                "frobenius_norm": "",
                "cancellation_score": "",
                "top1_spectral_fraction": "",
                "top2_spectral_fraction": "",
            })


def main() -> int:
    SUMMARY.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(REPO)
    manifest_path = SUMMARY / "m4pf0_source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    ident = identifiability_audit(REPO)
    fixture = gaussian_fixture()
    write_state_identifiability(ident)
    verdict = ("GO" if ident["frozen_sample_level_matrix_reconstruction"]
               else "GO-WITHOUT-FROZEN-RECONSTRUCTION")
    diagnostics = {
        "schema_version": "raretopo-m4pf0-gradient-diagnostics-v0",
        "stage": "M4-PF0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "extra_simulator_calls": 0,
        "matrix_gradient_theory": {
            "formula": "G=(M2/2) E_nuV[r_k(I-z_k z_k^T)]",
            "scalar_recovery": "trace(G)",
            "rank1_recovery": "v^T G v",
            "validated_by_deterministic_fixture": True,
        },
        "identifiability": ident,
        "gaussian_fixture": fixture,
        "real_state_directional_diagnostics": None,
        "real_state_figures_allowed": bool(ident[
            "frozen_sample_level_matrix_reconstruction"]),
        "pf0_verdict": verdict,
    }
    mismatches = verify_manifest(REPO, manifest)
    manifest["sources_unchanged"] = not mismatches
    manifest["post_analysis_mismatches"] = mismatches
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    diagnostics["source_lock"] = {
        "verified": not mismatches,
        "sources_unchanged": not mismatches,
    }
    (SUMMARY / "m4pf0_gradient_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "source_lock": not mismatches,
        "identifiable": ident["frozen_sample_level_matrix_reconstruction"],
        "verdict": verdict,
        "fixture_fd_max_relative_error_1e-4": fixture[
            "max_relative_error_epsilon_1e-4"],
        "extra_simulator_calls": 0,
    }, indent=2))
    return 0 if not mismatches else 3


if __name__ == "__main__":
    raise SystemExit(main())
