"""Zero-simulator corrected reanalysis of persisted PF2/PF3 archives."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from hyptraj.event_semantics import event_indicator_from_topology
from hyptraj.m1d.experiments import config_from_record
from hyptraj.m3.covariance_gradient import MixtureSpec, mixture_log_density
from hyptraj.m3.gradient_estimator import variance_mass_importance
from hyptraj.m4pf.gradient import matrix_gradient_estimate
from hyptraj.m4pf2.mean_gradient import mean_gradient_estimate
from hyptraj.m4pf3.diagnostics import allocation_diagnostics, coverage_diagnostics


SCHEMA_VERSION = 2


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _context(repo: Path, stage: str) -> tuple[dict[str, Any], dict[str, str], Path]:
    freeze = _json(repo / "docs/phase_m1d/M1_D_Benchmark_Freeze.json")
    configs = {row["config_id"]: row for row in freeze["benchmark_configs"]}
    raw_path = repo / f"results/phase_{stage}/m{stage[1:]}_confirmation_raw.json"
    raw = _json(raw_path)
    mapping = {row["state_id"]: row["state_key"]["config_id"] for row in raw["states"]}
    return configs, mapping, raw_path


def _corrected_mass(samples: np.ndarray, strata: np.ndarray, identity: dict,
                    bench) -> tuple[np.ndarray, np.ndarray]:
    pi = np.asarray(identity["weights"], dtype=float)
    means = np.asarray(identity["centers"], dtype=float)
    covs = tuple(np.asarray(value, dtype=float) for value in identity["covariances"])
    logp = np.asarray(bench.logp(samples), dtype=float)
    logq = mixture_log_density(MixtureSpec(pi, means, covs), samples)
    logr = np.where(np.asarray(strata, dtype=int) == 0, logp, logq)
    indicator = event_indicator_from_topology(bench.label(samples))
    mass = variance_mass_importance(samples, pi, means, covs, logp, logr,
                                    indicator.astype(float))
    return mass, indicator


def reanalyze_pf2(repo: Path, repair_commit: str) -> dict[str, Any]:
    configs, mapping, raw_path = _context(repo, "m4pf2")
    archive_dir = repo / "results/phase_m4pf2/gradient_samples/confirmation"
    rows = []
    for path in sorted(archive_dir.glob("*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            samples = archive["samples"]
            legacy = archive["variance_mass"]
            responsibility = archive["responsibility"]
            whitened = archive["whitened"]
            strata = archive["source_strata"]
            identity = json.loads(str(archive["proposal_identity"].item()))
        bench = config_from_record(configs[mapping[path.stem]])
        corrected, indicator = _corrected_mass(samples, strata, identity, bench)
        legacy_mean = float(np.mean(legacy))
        corrected_mean = float(np.mean(corrected))
        mean_grad = mean_gradient_estimate(corrected, responsibility, whitened)
        cov_grad = matrix_gradient_estimate(corrected, responsibility, whitened)
        rows.append({
            "state_id": path.stem,
            "legacy_source_path": path.relative_to(repo).as_posix(),
            "legacy_source_sha256": _sha(path),
            "repair_commit": repair_commit,
            "corrected_schema_version": SCHEMA_VERSION,
            "event_sample_fraction": float(np.mean(indicator)),
            "legacy_variance_mass_mean": legacy_mean,
            "corrected_variance_mass_mean": corrected_mean,
            "corrected_to_legacy_mass_ratio": corrected_mean / legacy_mean,
            "legacy_mass_on_true_event_fraction": float(legacy[indicator].sum() / legacy.sum()),
            "corrected_non_event_mass_max": float(np.max(corrected[~indicator])) if np.any(~indicator) else 0.0,
            "corrected_mean_gradient_norm": float(mean_grad["norm"]),
            "corrected_cov_gradient_trace": float(cov_grad["scalar_trace"]),
            "corrected_cov_gradient_frobenius_norm": float(np.linalg.norm(cov_grad["gradient_matrix"])),
            "corrected_gradient_ess": float(cov_grad["ESS_gradient"]),
        })
    out = repo / "results/evidence_repair/reanalysis/M4-PF2"
    _write_csv(out / "pf2_archive_legacy_vs_corrected.csv", rows)
    summary = {
        "stage": "M4-PF2",
        "status": "DIAGNOSTIC_REANALYSIS_ONLY_PARENT_NOT_AUTHORIZED",
        "legacy_source_path": raw_path.relative_to(repo).as_posix(),
        "legacy_source_sha256": _sha(raw_path),
        "repair_commit": repair_commit,
        "corrected_schema_version": SCHEMA_VERSION,
        "state_count": len(rows),
        "median_corrected_to_legacy_mass_ratio": float(np.median([row["corrected_to_legacy_mass_ratio"] for row in rows])),
        "median_legacy_mass_on_true_event_fraction": float(np.median([row["legacy_mass_on_true_event_fraction"] for row in rows])),
        "corrected_non_event_mass_max": float(max(row["corrected_non_event_mass_max"] for row in rows)),
        "final_evaluation_repairable_from_raw": False,
        "child_authorized": False,
        "extra_simulator_calls": 0,
    }
    _write_json(out / "pf2_reanalysis_summary.json", summary)
    return summary


def reanalyze_pf3(repo: Path, repair_commit: str) -> dict[str, Any]:
    configs, mapping, raw_path = _context(repo, "m4pf3")
    archive_dir = repo / "results/phase_m4pf3/gradient_samples/confirmation"
    rows = []
    for path in sorted(archive_dir.glob("*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            samples = archive["samples"]
            legacy = archive["variance_mass"]
            responsibilities = archive["responsibilities"]
            strata = archive["source_strata"]
            identity = json.loads(str(archive["proposal_identity"].item()))
        bench = config_from_record(configs[mapping[path.stem]])
        corrected, indicator = _corrected_mass(samples, strata, identity, bench)
        alpha = np.asarray(identity["weights"], dtype=float)
        allocation = allocation_diagnostics(corrected, responsibilities, alpha)
        covs = tuple(np.asarray(value, dtype=float) for value in identity["covariances"])
        coverage = coverage_diagnostics(samples, corrected,
                                        np.asarray(identity["centers"], dtype=float),
                                        covs, strata)[0]
        legacy_mean = float(np.mean(legacy))
        corrected_mean = float(np.mean(corrected))
        rows.append({
            "state_id": path.stem,
            "legacy_source_path": path.relative_to(repo).as_posix(),
            "legacy_source_sha256": _sha(path),
            "repair_commit": repair_commit,
            "corrected_schema_version": SCHEMA_VERSION,
            "event_sample_fraction": float(np.mean(indicator)),
            "legacy_variance_mass_mean": legacy_mean,
            "corrected_variance_mass_mean": corrected_mean,
            "corrected_to_legacy_mass_ratio": corrected_mean / legacy_mean,
            "legacy_mass_on_true_event_fraction": float(legacy[indicator].sum() / legacy.sum()),
            "corrected_non_event_mass_max": float(np.max(corrected[~indicator])) if np.any(~indicator) else 0.0,
            "legacy_A_alloc": float(np.max(np.abs(np.sum((legacy / legacy.sum())[:, None] * responsibilities, axis=0) - alpha))),
            "corrected_A_alloc": float(allocation["A_alloc"]),
            "corrected_U99": float(coverage["U99"]),
            "corrected_U999": float(coverage["U999"]),
        })
    out = repo / "results/evidence_repair/reanalysis/M4-PF3"
    _write_csv(out / "pf3_archive_legacy_vs_corrected.csv", rows)
    summary = {
        "stage": "M4-PF3",
        "status": "DIAGNOSTIC_REANALYSIS_ONLY_PARENT_NOT_AUTHORIZED",
        "legacy_source_path": raw_path.relative_to(repo).as_posix(),
        "legacy_source_sha256": _sha(raw_path),
        "repair_commit": repair_commit,
        "corrected_schema_version": SCHEMA_VERSION,
        "state_count": len(rows),
        "median_corrected_to_legacy_mass_ratio": float(np.median([row["corrected_to_legacy_mass_ratio"] for row in rows])),
        "median_legacy_mass_on_true_event_fraction": float(np.median([row["legacy_mass_on_true_event_fraction"] for row in rows])),
        "median_corrected_A_alloc": float(np.median([row["corrected_A_alloc"] for row in rows])),
        "median_corrected_U99": float(np.median([row["corrected_U99"] for row in rows])),
        "corrected_non_event_mass_max": float(max(row["corrected_non_event_mass_max"] for row in rows)),
        "final_evaluation_repairable_from_raw": False,
        "child_authorized": False,
        "extra_simulator_calls": 0,
    }
    _write_json(out / "pf3_reanalysis_summary.json", summary)
    return summary


def run_raw_reanalysis(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    repair_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--",
         "src/hyptraj/event_semantics.py"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "M4-PF2": reanalyze_pf2(repo, repair_commit),
        "M4-PF3": reanalyze_pf3(repo, repair_commit),
        "extra_simulator_calls": 0,
    }
