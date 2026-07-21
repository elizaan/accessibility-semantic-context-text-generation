"""
Assembles the paper deliverables from the CSVs the other scripts produce:
one flag-distribution table, one figure (speculation volume V1->V4 per
model), the misattribution table, one bootstrap-CI table per RQ
(RQ1 accessible-context, RQ2 image contribution, RQ3 missing-context
disclosure), the caution-measures table, the value-fidelity human-audit
table, and a handful of auto-picked qualitative failure excerpts for you
to curate down to 2-3.

Reads existing CSVs rather than recomputing anything, so run the other
scripts first (or just use run_all.py, which does that in order).

Usage (from backend/): python -m evaluation.report
"""

from __future__ import annotations

from evaluation.common import OUT_DIR, load_records, read_csv as _read_csv

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)


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


_RQ_CAVEAT = (
    "Charts were purposively sampled, not randomly drawn from a defined population. "
    "These bootstrap CIs describe resampling variability of the observed paired "
    "differences among the charts actually run — they are not a claim about sampling "
    "error relative to some larger population of charts. A CI that excludes 0 should be "
    "read as \"consistent, in this direction, across the charts we have,\" not as "
    "statistical generalizability. Rows marked `*` have n_pairs < 10 — read with extra caution.\n"
)

_RQ_TABLES = [
    ("RQ1_accessible_context", "RQ1: Accessible-Context Effect (V1 vs V3 — same image, context added)",
     "rq1_accessible_context_table.md"),
    ("RQ2_image_contribution", "RQ2: Image Contribution (V1 vs V2 — same context, image added)",
     "rq2_image_contribution_table.md"),
    ("RQ3_missing_context_disclosure", "RQ3: Missing-Context Disclosure (V3 vs V4 — same evidence, disclosure added)",
     "rq3_missing_context_disclosure_table.md"),
]


def build_rq_tables() -> None:
    rows = _read_csv(OUT_DIR / "paired_contrasts_bootstrap.csv")
    cols = ["model_id", "metric", "n_pairs", "mean_a", "mean_b", "mean_diff", "ci_lo", "ci_hi"]
    for contrast, title, filename in _RQ_TABLES:
        contrast_rows = [r for r in rows if r["contrast"] == contrast]
        # Mark low-n rows with a leading '*' on n_pairs rather than dropping
        # them — "keep inferential claims modest" means surfacing this
        # visibly, not hiding the row.
        display_rows = []
        for r in contrast_rows:
            r = dict(r)
            if r.get("low_n_flag") == "True":
                r["n_pairs"] = f"{r['n_pairs']}*"
            display_rows.append(r)
        md = f"# {title}\n\n{_RQ_CAVEAT}\n" + _markdown_table(display_rows, cols) + "\n"
        (REPORT_DIR / filename).write_text(md)
        print(f"[report] wrote {REPORT_DIR / filename}")


def build_caution_measures_table() -> None:
    rows = _read_csv(OUT_DIR / "caution_measures_summary.csv")
    cols = ["model_id", "variant", "n_records", "mean_hedging", "mean_abstention",
            "mean_missing_info_request", "mean_unsupported_causal", "total_markers_per_100_words"]
    md = ("# Caution / Metacognition Markers (model x variant)\n\n"
          "Direct measurement of RQ3's construct (does disclosing missing context change "
          "behavior?) via predefined regex/keyword marker categories — see "
          "evaluation/caution_measures.py for the exact phrase lists and their documented "
          "limitations. Complements, rather than replaces, the proxy measures (output "
          "length, claim volume) elsewhere in this report.\n\n" + _markdown_table(rows, cols) + "\n")
    (REPORT_DIR / "caution_measures_table.md").write_text(md)
    print(f"[report] wrote {REPORT_DIR / 'caution_measures_table.md'}")


def build_value_fidelity_audit_table() -> None:
    path = OUT_DIR / "value_fidelity_scored_audit.csv"
    if not path.exists():
        md = ("# Value-Fidelity Human Audit — not yet annotated\n\n"
              "Run `python -m evaluation.value_fidelity sample` to generate "
              "`value_fidelity_audit_sample.csv`, have two annotators fill in "
              "`annotator1_valid`/`annotator2_valid`, then `python -m evaluation.value_fidelity "
              "score evaluation/out/value_fidelity_audit_sample.csv` to produce this table.\n")
        (REPORT_DIR / "value_fidelity_audit_table.md").write_text(md)
        print(f"[report] wrote {REPORT_DIR / 'value_fidelity_audit_table.md'} (pending annotation)")
        return

    rows = _read_csv(path)
    cols = ["n_double_annotated", "cohens_kappa", "false_positive_rate", "false_positive_n",
            "false_negative_rate", "false_negative_n", "fp_rate_tuple_verified_yes",
            "fp_rate_tuple_verified_not_yes"]
    md = ("# Value-Fidelity Human Audit\n\n"
          "False-positive rate: sampled claims the automated checker called `correct` that both "
          "annotators independently judged `invalid`. False-negative rate: sampled claims called "
          "`fabricated` that both annotators judged `valid`. The two `tuple_verified` columns are "
          "the direct, quantified answer to whether the category/series-aware tuple check (vs. the "
          "flat value-only check) actually reduces the false-positive rate.\n\n"
          + _markdown_table(rows, cols) + "\n")
    (REPORT_DIR / "value_fidelity_audit_table.md").write_text(md)
    print(f"[report] wrote {REPORT_DIR / 'value_fidelity_audit_table.md'}")


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
    build_rq_tables()
    build_caution_measures_table()
    build_value_fidelity_audit_table()
    build_qualitative_excerpts()
    print(f"\n[report] all deliverables in {REPORT_DIR}")


if __name__ == "__main__":
    main()
