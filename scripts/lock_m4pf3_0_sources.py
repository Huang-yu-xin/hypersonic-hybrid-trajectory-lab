"""Create the deterministic PF3-0 read-only source manifest without analysis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
DESTINATION = (
    REPO / "results" / "phase_m4pf3_0" / "summary"
    / "m4pf3_0_source_manifest.json"
)

PF2_COMMIT = "82e6f36438fa1db6cf0b10055c16b573c07dd6b9"
PF1_COMMIT = "e6885bb59a8437cd5834a3a60ccf07c9c89624fe"
M3CA_COMMIT = "6b1ce6e"
M3BV2_TAG = "RareTopo-M3-BV2-v0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry(relative: str, role: str, tag: str, commit: str,
          proposal_identity: dict | None = None) -> dict:
    path = REPO / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    row = {
        "path": relative,
        "sha256": sha256_file(path),
        "source_tag": tag,
        "source_commit": commit,
        "role": role,
        "read_only": True,
    }
    if proposal_identity is not None:
        row["proposal_identity"] = proposal_identity
    return row


def build_manifest() -> dict:
    fixed = [
        ("results/phase_m4pf2/m4pf2_confirmation_raw.json",
         "PF2 P00/P10/P01/P11 confirmation records"),
        ("results/phase_m4pf2/summary/m4pf2_family_summary.json",
         "PF2 family summary"),
        ("results/phase_m4pf2/summary/m4pf2_state_table.csv",
         "PF2 state table"),
        ("results/phase_m4pf2/summary/m4pf2_tail_diagnostics.csv",
         "PF2 tail diagnostics"),
        ("results/phase_m4pf2/summary/m4pf2_source_manifest.json",
         "PF2 source manifest"),
        ("configs/phase_m4pf2/m4pf2_protocol.json", "PF2 protocol lock"),
        ("configs/phase_m4pf2/m4pf2_states.json", "PF2 state lock"),
        ("configs/phase_m4pf2/m4pf2_seeds.json", "PF2 seed lock"),
    ]
    sources = [entry(path, role, "RareTopo-M4-PF2-v0", PF2_COMMIT)
               for path, role in fixed]
    sources.append(entry(
        "results/phase_m4pf1/summary/m4pf1_family_summary.json",
        "PF1 family summary", "RareTopo-M4-PF1-v0", PF1_COMMIT))
    for path, role in (
        ("configs/phase_m3ca/m3ca_analysis_lock.json",
         "M3-CA cost-analysis definition"),
        ("results/phase_m3ca/summary/m3ca_cost_attribution.json",
         "M3-CA cost attribution"),
    ):
        sources.append(entry(path, role, "RareTopo-M3-CA-v0", M3CA_COMMIT))
    sources.append(entry(
        "configs/phase_m3bv2/m3bv2_value_benchmark.json",
        "M3-BV2 frozen state definitions", M3BV2_TAG, "tag-peel-at-audit"))

    archive_dir = (
        REPO / "results" / "phase_m4pf2" / "gradient_samples"
        / "confirmation"
    )
    archives = sorted(archive_dir.glob("*.npz"))
    if len(archives) != 24:
        raise RuntimeError(f"expected 24 PF2 archives, found {len(archives)}")
    for path in archives:
        with np.load(path, allow_pickle=False) as data:
            identity = json.loads(str(data["proposal_identity"].item()))
        sources.append(entry(
            path.relative_to(REPO).as_posix(),
            "PF2 S0-anchor gradient archive",
            "RareTopo-M4-PF2-v0", PF2_COMMIT, identity))

    return {
        "schema_version": "raretopo-m4pf3-0-source-manifest-v0",
        "stage": "M4-PF3-0",
        "analysis_performed": False,
        "simulator_calls": 0,
        "source_count": len(sources),
        "sources": sources,
    }


def main() -> None:
    manifest = build_manifest()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "path": DESTINATION.relative_to(REPO).as_posix(),
        "source_count": manifest["source_count"],
        "sha256": sha256_file(DESTINATION),
        "simulator_calls": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
