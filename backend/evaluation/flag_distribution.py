"""
Flag distribution — counts/proportions of [DIRECT]/[DERIVED]/[SPECULATIVE]
per model x variant x output section, plus two derived metrics:

  groundedness_ratio  = (DIRECT + DERIVED) / total claims
  speculation_volume  = absolute SPECULATIVE count (not a proportion — a
                         model that generates 10 claims with 3 speculative
                         and one that generates 30 claims with 3 speculative
                         have the same speculation *volume* but very
                         different speculation *proportion*; report both,
                         since proportion alone can hide a flat absolute
                         count behind a shrinking denominator)

The per-section breakdown counts the inline [DIRECT]/[DERIVED]/[SPECULATIVE]
tags directly out of each section's own text (evaluation.common.count_inline_flags)
rather than cross-referencing the separate flags.*_claims lists against
section text via substring match. An earlier version did the substring-match
version and got a ~100% "unmatched" rate for gpt-5.4 specifically — that
model paraphrases when populating the claims lists instead of keeping them
verbatim-synced with the inline-tagged text, which silently broke matching
for it while working fine for the other two models. Reading the inline
tags sidesteps that failure mode entirely (see section_speculation.py,
which hit this first).

Usage (from backend/): python -m evaluation.flag_distribution
"""

from __future__ import annotations

from collections import defaultdict

from evaluation.common import OUT_DIR, SECTION_KEYS, count_inline_flags, load_records, write_csv

FLAG_KINDS = ("direct", "derived", "speculative")


def main() -> None:
    records = load_records()
    parsed = [r for r in records if r.parse_ok]
    skipped = len(records) - len(parsed)
    if skipped:
        print(f"[flag_distribution] skipping {skipped} record(s) with unparsed output")

    # ── Per (model, variant, section) ──────────────────────────────────────
    section_counts: dict[tuple[str, int, str], dict[str, int]] = defaultdict(
        lambda: {"direct": 0, "derived": 0, "speculative": 0}
    )
    section_records: dict[tuple[str, int], set[str]] = defaultdict(set)

    for r in parsed:
        for section in SECTION_KEYS:
            text = r.sections.get(section, "")
            if not text:
                continue
            counts = count_inline_flags(text)
            bucket = section_counts[(r.model_id, r.variant, section)]
            for kind, n in counts.items():
                bucket[kind] += n
        section_records[(r.model_id, r.variant)].add(r.output_id)

    section_rows = []
    for (model_id, variant, section), counts in sorted(section_counts.items()):
        total = sum(counts.values())
        n_records = len(section_records[(model_id, variant)])
        section_rows.append({
            "model_id": model_id,
            "variant": variant,
            "section": section,
            "n_records": n_records,
            "direct": counts["direct"],
            "derived": counts["derived"],
            "speculative": counts["speculative"],
            "total_claims": total,
            "direct_pct": round(100 * counts["direct"] / total, 1) if total else "",
            "derived_pct": round(100 * counts["derived"] / total, 1) if total else "",
            "speculative_pct": round(100 * counts["speculative"] / total, 1) if total else "",
        })

    write_csv(
        OUT_DIR / "flag_distribution_by_section.csv",
        ["model_id", "variant", "section", "n_records", "direct", "derived", "speculative",
         "total_claims", "direct_pct", "derived_pct", "speculative_pct"],
        section_rows,
    )

    # ── Per (model, variant) summary — the headline table ──────────────────
    groups: dict[tuple[str, int], list] = defaultdict(list)
    for r in parsed:
        groups[(r.model_id, r.variant)].append(r)

    summary_rows = []
    for (model_id, variant), recs in sorted(groups.items()):
        direct_total = sum(len(r.direct_claims) for r in recs)
        derived_total = sum(len(r.derived_claims) for r in recs)
        speculative_total = sum(len(r.speculative_claims) for r in recs)
        total = direct_total + derived_total + speculative_total
        n = len(recs)
        summary_rows.append({
            "model_id": model_id,
            "variant": variant,
            "variant_label": recs[0].variant_label,
            "n_records": n,
            "direct_total": direct_total,
            "derived_total": derived_total,
            "speculative_total": speculative_total,
            "total_claims": total,
            "groundedness_ratio": round((direct_total + derived_total) / total, 3) if total else "",
            "speculation_volume_total": speculative_total,
            "speculation_volume_per_record": round(speculative_total / n, 2) if n else "",
        })

    write_csv(
        OUT_DIR / "flag_distribution_summary.csv",
        ["model_id", "variant", "variant_label", "n_records", "direct_total", "derived_total",
         "speculative_total", "total_claims", "groundedness_ratio",
         "speculation_volume_total", "speculation_volume_per_record"],
        summary_rows,
    )

    print("\nPreview (model x variant summary):")
    header = f"{'model':38s} {'V':>2s} {'n':>4s} {'direct':>7s} {'derived':>8s} {'specul.':>8s} {'grounded':>9s} {'spec/rec':>9s}"
    print(header)
    for row in summary_rows:
        print(
            f"{row['model_id']:38s} {row['variant']:>2d} {row['n_records']:>4d} "
            f"{row['direct_total']:>7d} {row['derived_total']:>8d} {row['speculative_total']:>8d} "
            f"{str(row['groundedness_ratio']):>9s} {str(row['speculation_volume_per_record']):>9s}"
        )


if __name__ == "__main__":
    main()
