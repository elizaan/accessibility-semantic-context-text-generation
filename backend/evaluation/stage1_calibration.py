"""
Stage-1 calibration: does a model's self-reported 0-5 completeness score
for each dimension actually track whether that dimension's information was
present in the prompt?

Ground-truth "was it actually available" per dimension is a heuristic
mapping from dimension -> which prompt fields feed it, since the three
dimensions don't correspond 1:1 to a single toggleable feature:

  data_values           <- data_table
  trend_magnitude       <- data_table OR l2_caption OR l3_caption
  chart_subject_domain  <- chart_title (shown unless variant == 3) OR domain_context

This is a proxy, not ground truth about what the model could *actually*
perceive (e.g. chart_subject_domain might be visually inferable from the
image even with a score of 0 available here) — treat the correlation as a
first-pass signal, not a precise measurement. It's documented here exactly
so that's inspectable rather than assumed.

Report: Pearson correlation between self-score and availability per model
x dimension, plus the specific overconfidence signal that's actually
clean: high (>=3) self-scores on `data_values` in V3/V4, where the exact
data table was, by construction, never available.

Usage (from backend/): python -m evaluation.stage1_calibration
"""

from __future__ import annotations

from collections import defaultdict

from evaluation.common import OUT_DIR, load_records, write_csv


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    varx = sum((x - mx) ** 2 for x in xs)
    vary = sum((y - my) ** 2 for y in ys)
    if varx == 0 or vary == 0:
        return None
    return cov / (varx * vary) ** 0.5


def _availability(r) -> dict[str, int]:
    feats = set(r.enabled_features)
    has_data_table = "data_table" in feats
    has_trend_source = has_data_table or "l2_caption" in feats or "l3_caption" in feats
    title_shown = r.variant != 3 and r.variant != 4 and bool(r.chart_title)
    has_domain = title_shown or "domain_context" in feats

    # Variant 4 (withheld) shows nothing regardless of enabled_features —
    # the request-level features are ignored by the prompt for that variant.
    if r.variant == 4:
        return {"data_values": 0, "trend_magnitude": 0, "chart_subject_domain": 0}

    return {
        "data_values": int(has_data_table),
        "trend_magnitude": int(has_trend_source),
        "chart_subject_domain": int(has_domain),
    }


def main() -> None:
    records = [r for r in load_records() if r.parse_ok and r.scores]

    by_model_dim: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)
    for r in records:
        avail = _availability(r)
        for dim, avail_flag in avail.items():
            if dim in r.scores:
                by_model_dim[(r.model_id, dim)].append((r.scores[dim], avail_flag))

    corr_rows = []
    for (model_id, dim), pairs in sorted(by_model_dim.items()):
        scores = [p[0] for p in pairs]
        avail = [p[1] for p in pairs]
        r = _pearson(scores, avail)
        mean_when_available = (
            round(sum(s for s, a in pairs if a == 1) / max(sum(avail), 1), 2) if sum(avail) else None
        )
        mean_when_absent = (
            round(sum(s for s, a in pairs if a == 0) / max(len(avail) - sum(avail), 1), 2)
            if len(avail) - sum(avail) else None
        )
        corr_rows.append({
            "model_id": model_id,
            "dimension": dim,
            "n": len(pairs),
            "pearson_r": round(r, 3) if r is not None else "",
            "mean_score_when_available": mean_when_available,
            "mean_score_when_absent": mean_when_absent,
        })

    write_csv(
        OUT_DIR / "stage1_calibration.csv",
        ["model_id", "dimension", "n", "pearson_r", "mean_score_when_available", "mean_score_when_absent"],
        corr_rows,
    )

    # ── The clean overconfidence signal: data_values >= 3 in V3/V4 ─────────
    overconfidence_rows = []
    by_model_v34 = defaultdict(list)
    for r in records:
        if r.variant in (3, 4) and "data_values" in r.scores:
            by_model_v34[r.model_id].append(r.scores["data_values"])

    for model_id, scores in sorted(by_model_v34.items()):
        n = len(scores)
        overconfident = sum(1 for s in scores if s >= 3)
        overconfidence_rows.append({
            "model_id": model_id,
            "n_records_v3_v4": n,
            "overconfident_count": overconfident,
            "overconfident_pct": round(100 * overconfident / n, 1) if n else "",
            "mean_data_values_score": round(sum(scores) / n, 2) if n else "",
        })

    write_csv(
        OUT_DIR / "stage1_overconfidence_v3v4.csv",
        ["model_id", "n_records_v3_v4", "overconfident_count", "overconfident_pct", "mean_data_values_score"],
        overconfidence_rows,
    )

    print("\nCalibration (Pearson r between self-score and actual availability):")
    for row in corr_rows:
        print(f"  {row['model_id']:38s} {row['dimension']:22s} r={row['pearson_r']!s:>7s}  n={row['n']}")

    print("\nOverconfidence signal — data_values score >= 3 despite no data table (V3/V4 only):")
    for row in overconfidence_rows:
        print(f"  {row['model_id']:38s} {row['overconfident_count']}/{row['n_records_v3_v4']} "
              f"({row['overconfident_pct']}%) mean={row['mean_data_values_score']}")


if __name__ == "__main__":
    main()
