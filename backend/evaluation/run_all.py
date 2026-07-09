"""
Runs the full automated pipeline in order. Skips the human steps —
provenance_audit's `sample`/`score` and l4_fidelity's human rubric CSV
still need you (or annotators) in the loop, this just generates the inputs
for that and everything that's fully automatable.

Usage (from backend/): python -m evaluation.run_all
"""

from __future__ import annotations

from evaluation import (
    flag_distribution,
    l4_fidelity,
    output_length,
    paired_contrasts,
    provenance_audit,
    report,
    section_speculation,
    stage1_calibration,
    value_fidelity,
)


def main() -> None:
    steps = [
        ("flag_distribution", flag_distribution.main),
        ("section_speculation", section_speculation.main),
        ("output_length", output_length.main),
        ("paired_contrasts", paired_contrasts.main),
        ("stage1_calibration", stage1_calibration.main),
        ("value_fidelity", value_fidelity.main),
        ("provenance_audit (automated)", provenance_audit.run_automated),
        ("provenance_audit (sample generation)", lambda: provenance_audit.run_sample(0.12, 0)),
        ("l4_fidelity", l4_fidelity.main),
        ("report", report.main),
    ]

    for name, fn in steps:
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        fn()

    print("\nDone. Human steps still needed:")
    print("  1. Annotate evaluation/out/provenance_audit_sample.csv (2 annotators),")
    print("     then: python -m evaluation.provenance_audit score evaluation/out/provenance_audit_sample.csv")
    print("  2. Fill in the rubric columns in evaluation/out/l4_fidelity_human_rubric.csv")
    print("  3. Curate evaluation/out/report/qualitative_excerpts.md down to 2-3 excerpts")


if __name__ == "__main__":
    main()
