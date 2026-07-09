"""
Assembles the paper deliverables from the CSVs the other scripts produce:
one flag-distribution table, one figure (speculation volume V1->V4 per
model), the misattribution table, the two paired deltas, and a handful of
auto-picked qualitative failure excerpts for you to curate down to 2-3.

Reads existing CSVs rather than recomputing anything, so run the other
scripts first (or just use run_all.py, which does that in order).

Usage (from backend/): python -m evaluation.report
"""

from __future__ import annotations

import csv

from evaluation.common import OUT_DIR, load_records

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)


def _read_csv(path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"[report] missing {path.relative_to(OUT_DIR.parent)} — "
                          f"run the corresponding script first (see run_all.py).")
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _markdown_table(rows: list[dict], columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return "\n".join(lines)


def build_flag_distribution_table() -> None:
    rows = _read_csv(OUT_DIR / "flag_distribution_summary.csv")
    cols = ["model_id", "variant_label", "n_records", "direct_total", "derived_total",
            "speculative_total", "groundedness_ratio", "speculation_volume_per_record"]
    md = "# Flag Distribution (model x variant)\n\n" + _markdown_table(rows, cols) + "\n"
    (REPORT_DIR / "flag_distribution_table.md").write_text(md)
    print(f"[report] wrote {REPORT_DIR / 'flag_distribution_table.md'}")


def build_speculation_volume_figure() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = _read_csv(OUT_DIR / "flag_distribution_summary.csv")
    models = sorted({r["model_id"] for r in rows})
    variants = sorted({int(r["variant"]) for r in rows})

    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.8 / len(models)
    for i, model in enumerate(models):
        ys = []
        for v in variants:
            match = next((r for r in rows if r["model_id"] == model and int(r["variant"]) == v), None)
            ys.append(float(match["speculation_volume_per_record"]) if match and match["speculation_volume_per_record"] else 0)
        xs = [v + i * width for v in variants]
        ax.bar(xs, ys, width=width, label=model.split("/")[-1])

    ax.set_xticks([v + width * (len(models) - 1) / 2 for v in variants])
    ax.set_xticklabels([f"V{v}" for v in variants])
    ax.set_xlabel("Variant")
    ax.set_ylabel("Speculative claims per output (mean)")
    ax.set_title("Speculation volume across V1→V4, per model")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "speculation_volume.png", dpi=150)
    plt.close(fig)
    print(f"[report] wrote {REPORT_DIR / 'speculation_volume.png'}")


def build_misattribution_table() -> None:
    rows = _read_csv(OUT_DIR / "provenance_automated_v3v4.csv")
    cols = ["model_id", "variant", "n_direct_claims", "n_title_excluded",
            "misattribution_rate_raw", "misattribution_rate_adjusted"]
    md = ("# V3/V4 Automated Misattribution Rate\n\n"
          "Any [DIRECT] claim in V3/V4 is a misattribution by construction (no metadata "
          "was ever provided). `_adjusted` excludes claims that plausibly reference the "
          "chart title — all current V3 data predates the chart_title-leak fix, so `_raw` "
          "overstates V3's rate; `_adjusted` is the fairer number until V3 is regenerated.\n\n"
          + _markdown_table(rows, cols) + "\n")
    (REPORT_DIR / "misattribution_table.md").write_text(md)
    print(f"[report] wrote {REPORT_DIR / 'misattribution_table.md'}")


def build_paired_deltas_table() -> None:
    rows = _read_csv(OUT_DIR / "paired_contrasts_deltas.csv")
    cols = ["model_id", "contrast", "speculative_total_delta", "direct_total_delta",
            "groundedness_ratio_delta", "speculation_volume_per_record_delta",
            "mean_score_overall_delta"]
    md = "# Paired Contrasts (V1<->V2 image effect, V3<->V4 framing effect)\n\n" + _markdown_table(rows, cols) + "\n"
    (REPORT_DIR / "paired_deltas_table.md").write_text(md)
    print(f"[report] wrote {REPORT_DIR / 'paired_deltas_table.md'}")


def build_qualitative_excerpts(n_per_model: int = 1) -> None:
    """
    Auto-picks candidate failure excerpts: for each model, the V1 record
    (full metadata + image — nothing missing) with the most speculative
    claims. Speculating when nothing is missing is the cleanest example of
    unnecessary fabrication to quote in a paper. These are candidates to
    curate down to 2-3, not a final selection — read them before using them.
    """
    records = [r for r in load_records(verbose=False) if r.parse_ok and r.variant == 1]
    by_model: dict[str, list] = {}
    for r in records:
        by_model.setdefault(r.model_id, []).append(r)

    lines = ["# Qualitative Failure Excerpts (candidates — curate down to 2-3)\n"]
    for model_id, recs in sorted(by_model.items()):
        recs.sort(key=lambda r: len(r.speculative_claims), reverse=True)
        for r in recs[:n_per_model]:
            lines.append(f"\n## {model_id} — {r.chart_id} (V1, {len(r.speculative_claims)} speculative claims despite full metadata)\n")
            lines.append(f"**Speculative claims:**\n")
            for c in r.speculative_claims[:5]:
                lines.append(f"- {c}")
            lines.append(f"\n**real_world_significance section:**\n\n> {r.sections.get('real_world_significance', '')}\n")

    (REPORT_DIR / "qualitative_excerpts.md").write_text("\n".join(lines))
    print(f"[report] wrote {REPORT_DIR / 'qualitative_excerpts.md'}")


def main() -> None:
    build_flag_distribution_table()
    build_speculation_volume_figure()
    build_misattribution_table()
    build_paired_deltas_table()
    build_qualitative_excerpts()
    print(f"\n[report] all deliverables in {REPORT_DIR}")


if __name__ == "__main__":
    main()
