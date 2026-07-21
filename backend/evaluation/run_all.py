"""
Runs the full automated pipeline in order. Skips the human steps —
provenance_audit's `sample`/`score`, value_fidelity's `sample`/`score`, and
l4_fidelity's human rubric CSV still need you (or annotators) in the loop,
this just generates the inputs for that and everything that's fully
automatable.

Ordering note: value_fidelity.run_automated() and caution_measures.main()
now run BEFORE paired_contrasts.main(), which reads both of their CSV
outputs (numeric_value_match_rate and the caution measures respectively)
to build its chart-paired RQ1/RQ2/RQ3 estimates — a real dependency that
didn't exist in the old aggregate-vs-aggregate version of paired_contrasts.

Usage (from backend/): python -m evaluation.run_all
"""

from __future__ import annotations

from evaluation import (
    caution_measures,
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
        ("value_fidelity (automated)", value_fidelity.run_automated),
        ("caution_measures", caution_measures.main),
        ("paired_contrasts", paired_contrasts.main),
        ("stage1_calibration", stage1_calibration.main),
        ("provenance_audit (automated)", provenance_audit.run_automated),
        ("provenance_audit (sample generation)", lambda: provenance_audit.run_sample(0.12, 0)),
        ("value_fidelity (sample generation)", lambda: value_fidelity.run_sample(30, 0)),
        ("l4_fidelity", l4_fidelity.main),
        ("report", report.main),
    ]

    for name, fn in steps:
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        fn()

    print("\nDone. Human steps still needed:")
    print("  1. Annotate evaluation/out/provenance_audit_sample.csv (2 annotators),")
    print("     then: python -m evaluation.provenance_audit score evaluation/out/provenance_audit_sample.csv")
    print("  2. Annotate evaluation/out/value_fidelity_audit_sample.csv (2 annotators),")
    print("     then: python -m evaluation.value_fidelity score evaluation/out/value_fidelity_audit_sample.csv")
    print("  3. Fill in the rubric columns in evaluation/out/l4_fidelity_human_rubric.csv")
    print("  4. Curate evaluation/out/report/qualitative_excerpts.md down to 2-3 excerpts")


if __name__ == "__main__":
    main()
