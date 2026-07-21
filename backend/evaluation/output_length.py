"""
Output length (word count) per section x variant x model — a second,
independent test of the same "unfaltering fluency" pattern
section_speculation.py surfaces, but one that needs no semantic judgment
at all: if a model keeps generating equally long, equally fluent output as
metadata is withdrawn (V1 -> V2/V3/V4) instead of visibly hedging or
truncating, that's confident fabrication showing up in the simplest
possible signal — it just keeps talking.

Word count = len(text.split()) per generated_description section. Reports:
  - mean total length per output (sum of all 4 sections) per model x
    variant — the headline comparison, same x-axis/grouping as
    report.py's speculation_volume.png so the two are directly comparable
    side by side.
  - mean length per individual section x variant x model — the fully
    resolved breakdown.

Usage (from backend/): python -m evaluation.output_length
"""

from __future__ import annotations

from collections import defaultdict

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, word_count, write_csv

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)

SECTION_TITLES = {
    "contextual_insights": "Contextual Insights",
    "domain_specific_explanations": "Domain-Specific Explanations",
    "real_world_significance": "Real-World Significance (L4)",
    "other": "Other",
}


def main() -> None:
    records = [r for r in load_records() if r.parse_ok]

    # ── total length per (model, variant) ───────────────────────────────
    totals: dict[tuple[str, int], list[int]] = defaultdict(list)
    # ── per (model, variant, section) ───────────────────────────────────
    by_section: dict[tuple[str, int, str], list[int]] = defaultdict(list)

    for r in records:
        total = 0
        for section in SECTION_KEYS:
            wc = word_count(r.sections.get(section, ""))
            by_section[(r.model_id, r.variant, section)].append(wc)
            total += wc
        totals[(r.model_id, r.variant)].append(total)

    # ── write CSVs ───────────────────────────────────────────────────────
    summary_rows = []
    for (model_id, variant), lengths in sorted(totals.items()):
        n = len(lengths)
        summary_rows.append({
            "model_id": model_id,
            "variant": variant,
            "n_records": n,
            "mean_total_words": round(sum(lengths) / n, 1) if n else "",
            "min_total_words": min(lengths) if lengths else "",
            "max_total_words": max(lengths) if lengths else "",
        })
    write_csv(OUT_DIR / "output_length_summary.csv",
              ["model_id", "variant", "n_records", "mean_total_words", "min_total_words", "max_total_words"],
              summary_rows)

    section_rows = []
    for (model_id, variant, section), lengths in sorted(by_section.items()):
        n = len(lengths)
        section_rows.append({
            "model_id": model_id,
            "variant": variant,
            "section": section,
            "n_records": n,
            "mean_words": round(sum(lengths) / n, 1) if n else "",
        })
    write_csv(OUT_DIR / "output_length_by_section.csv",
              ["model_id", "variant", "section", "n_records", "mean_words"], section_rows)

    # ── markdown table ───────────────────────────────────────────────────
    md_lines = ["# Output Length (mean word count per output, by model x variant)\n",
                "Tests the same 'unfaltering fluency' pattern as speculation volume, but with "
                "no semantic judgment needed: if length stays flat as metadata drops (V1->V4), "
                "the model isn't visibly hedging or truncating when it has less to say.\n",
                "| model_id | variant | n_records | mean_total_words | min | max |",
                "| --- | --- | --- | --- | --- | --- |"]
    for row in summary_rows:
        md_lines.append(f"| {row['model_id']} | {row['variant']} | {row['n_records']} | "
                         f"{row['mean_total_words']} | {row['min_total_words']} | {row['max_total_words']} |")
    (REPORT_DIR / "output_length_table.md").write_text("\n".join(md_lines) + "\n")
    print(f"[output_length] wrote {REPORT_DIR / 'output_length_table.md'}")

    # ── plots ────────────────────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = sorted({m for m, _ in totals})
    variants = sorted({v for _, v in totals})

    # total length, V1->V4 per model — directly comparable to speculation_volume.png
    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.8 / len(models)
    for i, model in enumerate(models):
        ys = [sum(totals.get((model, v), [0])) / len(totals[(model, v)]) if totals.get((model, v)) else 0
              for v in variants]
        xs = [v + i * width for v in variants]
        ax.bar(xs, ys, width=width, label=model.split("/")[-1])
    ax.set_xticks([v + width * (len(models) - 1) / 2 for v in variants])
    ax.set_xticklabels([f"V{v}" for v in variants])
    ax.set_xlabel("Variant")
    ax.set_ylabel("Mean total output length (words)")
    ax.set_title("Output length across V1→V4, per model")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "output_length_total.png", dpi=150)
    plt.close(fig)
    print(f"[output_length] wrote {REPORT_DIR / 'output_length_total.png'}")

    # per-section breakdown, 2x2 grid, x=variant within each panel, grouped by model
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, section in zip(axes.flat, SECTION_KEYS):
        width = 0.8 / len(models)
        for i, model in enumerate(models):
            ys = []
            for v in variants:
                lengths = by_section.get((model, v, section), [])
                ys.append(sum(lengths) / len(lengths) if lengths else 0)
            xs = [v + i * width for v in variants]
            ax.bar(xs, ys, width=width, label=model.split("/")[-1])
        ax.set_xticks([v + width * (len(models) - 1) / 2 for v in variants])
        ax.set_xticklabels([f"V{v}" for v in variants])
        ax.set_title(SECTION_TITLES[section], fontsize=11)
        ax.set_ylabel("Mean word count")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Output length by section, across V1→V4", fontsize=13)
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "output_length_by_section.png", dpi=150)
    plt.close(fig)
    print(f"[output_length] wrote {REPORT_DIR / 'output_length_by_section.png'}")

    print("\nMean total output length (words) per model x variant:")
    for row in summary_rows:
        print(f"  {row['model_id']:38s} V{row['variant']} mean={row['mean_total_words']:>6} "
              f"(min={row['min_total_words']}, max={row['max_total_words']})")


if __name__ == "__main__":
    main()
