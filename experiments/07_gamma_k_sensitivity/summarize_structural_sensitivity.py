"""F5 summarizer -- read-only view of the structural sensitivity map.

Reads ONLY ``results/gamma_k_sensitivity/structural_sensitivity/``.
"""

import json
import sys
from pathlib import Path

OUT_DIR = Path("results/gamma_k_sensitivity/structural_sensitivity")


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    summary = _load("f5_summary.json")
    stats = _load("regime_statistics.json")["statistics"]
    audit = _load("reference_audit.json")
    sign = _load("sign_structure.json")["sign_structure"]
    health = _load("field_health.json")["health"]

    print("F5 FIXED-TOPOLOGY STRUCTURAL SENSITIVITY -- READ-ONLY SUMMARY")
    print("=" * 72)
    print(f"git commit : {summary['git_commit']}")
    print(f"centers    : {summary['canonical_centers']}")

    print("\n## Derivative availability")
    for key, counts in summary["availability"].items():
        print(f"  {key}: {counts}")
    print(f"global gamma fraction: "
          f"{summary['global_policy_validation']['gamma_h_0.1_accepted_fraction']:.3f}")
    print(f"global K fraction    : "
          f"{summary['global_policy_validation']['K_h_0.025_accepted_fraction']:.3f}")

    print("\n## Qian structural ranges (per radian)")
    for out in ("qian_rti_range_m", "qian_rti_time_s",
                "qian_energy_loss_jpkg"):
        block = stats["qian"]["gamma"][out]["whole-domain"]
        print(f"  {out}: count={block['count']} "
              f"min={block['min']:.4g} median={block['median']:.4g} "
              f"max={block['max']:.4g} "
              f"sign={block['sign']}")

    print("\n## Sanger per-regime dR/dgamma (per radian)")
    print("| regime | count | min | median | max | sign |")
    print("|---|---|---|---|---|---|")
    for regime in sorted(stats["sanger"]["gamma"]["sanger_srti_range_m"]):
        b = stats["sanger"]["gamma"]["sanger_srti_range_m"][regime]
        print(f"| {regime} | {b['count']} | {b['min']:.4g} | "
              f"{b['median']:.4g} | {b['max']:.4g} | {b['sign']} |")

    print("\n## Sanger per-regime dR/dK (per unit K)")
    print("| regime | count | min | median | max | sign |")
    print("|---|---|---|---|---|---|")
    for regime in sorted(stats["sanger"]["K"]["sanger_srti_range_m"]):
        b = stats["sanger"]["K"]["sanger_srti_range_m"][regime]
        print(f"| {regime} | {b['count']} | {b['min']:.4g} | "
              f"{b['median']:.4g} | {b['max']:.4g} | {b['sign']} |")

    print("\n## Sanger terminal-time / energy sensitivity")
    for out in ("sanger_srti_time_s", "sanger_energy_loss_jpkg"):
        print(f"  {out} d/dgamma:")
        for regime in sorted(stats["sanger"]["gamma"][out]):
            b = stats["sanger"]["gamma"][out][regime]
            print(f"    {regime}: n={b['count']} median={b['median']:.4g} "
                  f"sign={b['sign']}")

    print("\n## Within-regime sign changes")
    for model in ("qian", "sanger"):
        for param in ("gamma", "K"):
            changes = []
            for out, info in sign[model][param].items():
                if info["within_regime_sign_change"]:
                    changes.append(
                        f"{out}->{info['within_regime_sign_change']}")
            print(f"  {model} {param}: {changes if changes else 'none'}")

    print("\n## Reference audit")
    print(f"  audited points: {audit['audited_points']} | "
          f"REF-0.05 subset: {audit['ref005_subset']}")

    print("\n## Field health")
    for key, h in health.items():
        jumps = sum(v["jump_count"] for v in h.values())
        print(f"  {key}: jumps={jumps}")

    print("\n## Ready for F6")
    print(f"  ready_for_F6: {summary['ready_for_F6']}")
    print("F5 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
