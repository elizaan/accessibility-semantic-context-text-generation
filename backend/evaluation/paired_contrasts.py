"""
Chart-paired, bootstrap-CI'd estimates for the three explicit research
questions this variant design answers:

  RQ1 accessible-context effect     V1 -> V3   same image; context added
  RQ2 image contribution            V1 -> V2   same context; image added
  RQ3 missing-context disclosure    V3 -> V4   same evidence; disclosure added

This REPLACES an earlier version of this script that only covered 2 of
these 3 contrasts (RQ1's V1<->V3 pair didn't exist at all) and computed
deltas between AGGREGATE stats — summed claim/score totals across every
record in a (model, variant) bucket, then subtracted the two buckets'
aggregate values. That's not a paired difference despite the design being
paired by chart: token-level totals can be dominated by a single verbose
model or a few number-heavy charts, and it produced no uncertainty
interval at all.

This version instead computes, for each model and each contrast, the
PER-CHART difference in each metric — b - a for every chart that has an
output at both variants — and reports a bootstrap confidence interval over
that list of paired differences (see evaluation.bootstrap for the method
and why percentile, not BCa). If a chart somehow has two output records
for the same (model, variant) — a regeneration — the one with the later
created_at is kept and a warning is printed; duplicates are never silently
summed or averaged.

Four metric groups (10 metric rows per model x contrast):

  1. Claim-label proportions (direct_proportion, derived_proportion,
     speculative_proportion) — via common.count_inline_flags summed
     across all 4 sections, divided by their total. Uses inline-tag
     counting, NOT len(record.direct_claims)/etc: this codebase's own
     documented caveat (see value_fidelity.py, flag_distribution.py) is
     that gpt-5.4 paraphrases when populating the flags.*_claims lists,
     so they don't verbatim-sync with the inline [DIRECT]/[DERIVED]/
     [SPECULATIVE] tags a human reader would actually see. NOTE: this is
     a deliberate, intentional split from flag_distribution.py and
     provenance_audit.py, which still use list-length for their own
     purposes — not migrated in this pass (see README's Known Data
     Caveats for why).

  2. claims_per_100_words — total inline-flag count / word count * 100.
     Controls for verbosity: a model that's simply more verbose shouldn't
     look more "grounded" purely from claim-count inflation.

  3. numeric_value_match_rate — read back from value_fidelity_claims.csv
     (this script must run AFTER `value_fidelity automated` — see
     run_all.py), re-aggregated to (chart_id, model_id, variant)
     granularity (value_fidelity_summary.csv is pre-aggregated to
     (model, variant) only, too coarse for chart-pairing). Only
     computable for the ~70% of charts value_fidelity itself can resolve
     a ground-truth source for — those charts are naturally excluded from
     THIS metric's pairing (n_pairs varies per metric, see below), not
     from the whole analysis.

  4. Caution/metacognition markers (evaluation.caution_measures) — a
     composite (caution_total_per_100_words) plus each of the 4
     sub-category rates as its own row, so RQ3's "did the model behave
     more cautiously" isn't collapsed into one opaque number.

n_pairs varies per (model, contrast, metric) row BY DESIGN — a chart
missing either side of a pair for one metric (e.g. outside
value_fidelity's scope) is simply excluded from that metric's pairing,
while still contributing to the other metrics where both sides exist. This
is always reported as a leading column, never hidden or reconciled away
across metrics.

Purposive-sampling caveat (repeated in report.py's generated tables, not
just here): charts were purposively sampled, not randomly drawn from a
defined population. These bootstrap CIs describe resampling variability of
the observed paired differences among the charts actually run — they are
not a claim about sampling error relative to some larger population of
charts. A CI that excludes 0 should be read as "consistent, in this
direction, across the charts we have," not as statistical generalizability.

`paired_contrasts_deltas.csv` (the old aggregate-vs-aggregate file) is
retired — not written by this version. `paired_contrasts_by_variant.csv`
(plain per-variant descriptive aggregates, not deltas) is unaffected and
still written, since it was never the flawed part.

Usage (from backend/): python -m evaluation.paired_contrasts
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from evaluation.bootstrap import bootstrap_ci
from evaluation.caution_measures import count_markers
from evaluation.common import OUT_DIR, SCORE_DIMENSIONS, SECTION_KEYS, count_inline_flags, load_records, read_csv, word_count, write_csv

CONTRASTS = [
    (1, 3, "RQ1_accessible_context"),
    (1, 2, "RQ2_image_contribution"),
    (3, 4, "RQ3_missing_context_disclosure"),
]

LOW_N_THRESHOLD = 10


# ── metric 1+2: label proportions and claims/100 words, from inline tags ───

def _full_text(record) -> str:
    return " ".join(record.sections.get(k, "") for k in SECTION_KEYS)


def _label_proportions(record) -> dict[str, float | None]:
    counts = count_inline_flags(_full_text(record))
    total = sum(counts.values())
    if total == 0:
        return {"direct_proportion": None, "derived_proportion": None, "speculative_proportion": None}
    return {
        "direct_proportion": counts["direct"] / total,
        "derived_proportion": counts["derived"] / total,
        "speculative_proportion": counts["speculative"] / total,
    }


def _claims_per_100_words(record) -> float | None:
    text = _full_text(record)
    counts = count_inline_flags(text)
    wc = word_count(text)
    return (100 * sum(counts.values()) / wc) if wc else None


# ── metric 4: caution markers, per 100 words ────────────────────────────────

def _caution_rates(record) -> dict[str, float | None]:
    text = _full_text(record)
    wc = word_count(text)
    counts = count_markers(record)
    if not wc:
        return {
            "caution_total_per_100_words": None, "caution_hedging_per_100_words": None,
            "caution_abstention_per_100_words": None, "caution_missing_info_per_100_words": None,
            "caution_unsupported_causal_per_100_words": None,
        }
    total = sum(counts.values())
    return {
        "caution_total_per_100_words": 100 * total / wc,
        "caution_hedging_per_100_words": 100 * counts["hedging"] / wc,
        "caution_abstention_per_100_words": 100 * counts["abstention"] / wc,
        "caution_missing_info_per_100_words": 100 * counts["missing_info_request"] / wc,
        "caution_unsupported_causal_per_100_words": 100 * counts["unsupported_causal"] / wc,
    }


# ── metric 3: numeric value-match rate, from value_fidelity's own output ───

def _load_value_match_rates() -> dict[tuple[str, str, int], float]:
    """(chart_id, model_id, variant) -> n_correct / n_checked, re-aggregated
    from value_fidelity_claims.csv's per-claim verdicts. Requires
    `python -m evaluation.value_fidelity automated` to have already run —
    see run_all.py, where this script now runs after it (a real ordering
    change from before, since this dependency didn't exist previously)."""
    rows = read_csv(OUT_DIR / "value_fidelity_claims.csv")
    counts: dict[tuple[str, str, int], list[int]] = defaultdict(lambda: [0, 0])  # [n_correct, n_total]
    for row in rows:
        key = (row["chart_id"], row["model_id"], int(row["variant"]))
        counts[key][1] += 1
        if row["verdict"] == "correct":
            counts[key][0] += 1
    return {key: (n_correct / n_total) for key, (n_correct, n_total) in counts.items() if n_total}


# ── plain per-variant descriptive aggregates (unchanged in spirit from the
# previous version — this file was never the flawed part) ──────────────────

def _aggregate(records: list) -> dict:
    n = len(records)
    direct_total = sum(len(r.direct_claims) for r in records)
    derived_total = sum(len(r.derived_claims) for r in records)
    speculative_total = sum(len(r.speculative_claims) for r in records)
    total_claims = direct_total + derived_total + speculative_total

    score_means = {}
    for dim in (*SCORE_DIMENSIONS, "overall"):
        vals = [r.scores[dim] for r in records if dim in r.scores]
        score_means[dim] = round(mean(vals), 3) if vals else None

    return {
        "n_records": n,
        "direct_total": direct_total,
        "derived_total": derived_total,
        "speculative_total": speculative_total,
        "groundedness_ratio": round((direct_total + derived_total) / total_claims, 3) if total_claims else None,
        "speculation_volume_per_record": round(speculative_total / n, 2) if n else None,
        "direct_per_record": round(direct_total / n, 2) if n else None,
        **{f"mean_score_{dim}": v for dim, v in score_means.items()},
    }


def _dedup_latest_per_chart(records: list) -> dict[str, object]:
    """chart_id -> record for one (model, variant) bucket, keeping the
    latest created_at if a chart somehow has two outputs for the same
    (model, variant) — never silently summed or averaged."""
    by_chart: dict[str, object] = {}
    for r in records:
        existing = by_chart.get(r.chart_id)
        if existing is None or r.created_at > existing.created_at:
            if existing is not None:
                print(f"[paired_contrasts] duplicate output for {r.chart_id}/{r.model_id}/V{r.variant} "
                      f"— keeping the one created_at={r.created_at}")
            by_chart[r.chart_id] = r
    return by_chart


def main() -> None:
    records = [r for r in load_records() if r.parse_ok]
    value_match_rates = _load_value_match_rates()

    by_model_variant: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        by_model_variant[r.model_id][r.variant].append(r)

    # ── plain per-variant table (unchanged purpose) ─────────────────────────
    variant_rows = []
    for model_id, by_variant in sorted(by_model_variant.items()):
        for variant, recs in sorted(by_variant.items()):
            variant_rows.append({"model_id": model_id, "variant": variant, **_aggregate(recs)})
    variant_fields = ["model_id", "variant", "n_records", "direct_total", "derived_total",
                       "speculative_total", "groundedness_ratio", "speculation_volume_per_record",
                       "direct_per_record"] + [f"mean_score_{d}" for d in (*SCORE_DIMENSIONS, "overall")]
    write_csv(OUT_DIR / "paired_contrasts_by_variant.csv", variant_fields, variant_rows)

    # ── chart-paired bootstrap analysis, per RQ ─────────────────────────────
    bootstrap_rows = []
    for model_id, by_variant in sorted(by_model_variant.items()):
        by_variant_charts = {v: _dedup_latest_per_chart(recs) for v, recs in by_variant.items()}

        for v_from, v_to, contrast in CONTRASTS:
            charts_a = by_variant_charts.get(v_from, {})
            charts_b = by_variant_charts.get(v_to, {})
            if not charts_a or not charts_b:
                print(f"[paired_contrasts] {model_id}: missing V{v_from} or V{v_to} entirely, skipping {contrast}")
                continue
            paired_ids = sorted(charts_a.keys() & charts_b.keys())

            metric_pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
            for cid in paired_ids:
                ra, rb = charts_a[cid], charts_b[cid]

                pa, pb = _label_proportions(ra), _label_proportions(rb)
                for key in ("direct_proportion", "derived_proportion", "speculative_proportion"):
                    if pa[key] is not None and pb[key] is not None:
                        metric_pairs[key].append((pa[key], pb[key]))

                ca, cb = _claims_per_100_words(ra), _claims_per_100_words(rb)
                if ca is not None and cb is not None:
                    metric_pairs["claims_per_100_words"].append((ca, cb))

                va = value_match_rates.get((cid, model_id, v_from))
                vb = value_match_rates.get((cid, model_id, v_to))
                if va is not None and vb is not None:
                    metric_pairs["numeric_value_match_rate"].append((va, vb))

                caution_a, caution_b = _caution_rates(ra), _caution_rates(rb)
                for key in caution_a:
                    if caution_a[key] is not None and caution_b[key] is not None:
                        metric_pairs[key].append((caution_a[key], caution_b[key]))

            for metric, pairs in metric_pairs.items():
                diffs = [b - a for a, b in pairs]
                result = bootstrap_ci(diffs)
                mean_a = round(mean(a for a, _ in pairs), 4) if pairs else ""
                mean_b = round(mean(b for _, b in pairs), 4) if pairs else ""
                bootstrap_rows.append({
                    "model_id": model_id,
                    "contrast": contrast,
                    "metric": metric,
                    "n_pairs": result["n"],
                    "mean_a": mean_a,
                    "mean_b": mean_b,
                    "mean_diff": result["mean_diff"] if result["mean_diff"] is not None else "",
                    "ci_lo": result["ci_lo"] if result["ci_lo"] is not None else "",
                    "ci_hi": result["ci_hi"] if result["ci_hi"] is not None else "",
                    "low_n_flag": result["n"] < LOW_N_THRESHOLD,
                })

    write_csv(
        OUT_DIR / "paired_contrasts_bootstrap.csv",
        ["model_id", "contrast", "metric", "n_pairs", "mean_a", "mean_b", "mean_diff", "ci_lo", "ci_hi", "low_n_flag"],
        bootstrap_rows,
    )

    print("\nChart-paired bootstrap differences (b - a; positive = higher at the second variant of the pair).")
    print("Charts were purposively sampled — read n_pairs, and treat these as descriptive of the charts")
    print("actually run, not as a population-level inference.\n")
    for row in bootstrap_rows:
        flag = " [LOW N]" if row["low_n_flag"] else ""
        print(f"  {row['model_id']:38s} {row['contrast']:32s} {row['metric']:38s} "
              f"n={row['n_pairs']:>3} diff={row['mean_diff']!s:>8} "
              f"CI=[{row['ci_lo']!s:>7}, {row['ci_hi']!s:>7}]{flag}")


if __name__ == "__main__":
    main()
