"""
The two paired contrasts this variant design was specifically built for:

  V1 <-> V2  image effect:   metadata held constant (full), image on vs off
  V3 <-> V4  framing effect: payload held constant (image only, nothing
                              else), the only difference is whether the
                              model is told metadata exists but was withheld

V3<->V4 is the headline metacognition result — does telling a model it's
missing something change its behavior at all? A model with a near-zero
delta between V3 and V4 is one whose fabrication rate doesn't depend on
whether it *knows* it's guessing, which is arguably worse than one that
gets more cautious when explicitly warned.

For each model, reports per-variant aggregates (speculation volume, direct
count, groundedness ratio, mean Stage-1 scores) and the two deltas.

Usage (from backend/): python -m evaluation.paired_contrasts
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from evaluation.common import OUT_DIR, SCORE_DIMENSIONS, load_records, write_csv

PAIRS = [(1, 2, "image_effect (V1->V2)"), (3, 4, "framing_effect (V3->V4)")]


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


def main() -> None:
    records = load_records()
    parsed = [r for r in records if r.parse_ok]

    by_model_variant: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for r in parsed:
        by_model_variant[r.model_id][r.variant].append(r)

    variant_rows = []
    delta_rows = []

    for model_id, by_variant in sorted(by_model_variant.items()):
        agg_by_variant = {v: _aggregate(recs) for v, recs in by_variant.items()}

        for variant, agg in sorted(agg_by_variant.items()):
            variant_rows.append({"model_id": model_id, "variant": variant, **agg})

        for v_from, v_to, label in PAIRS:
            if v_from not in agg_by_variant or v_to not in agg_by_variant:
                print(f"[paired_contrasts] {model_id}: missing V{v_from} or V{v_to}, skipping {label}")
                continue
            a, b = agg_by_variant[v_from], agg_by_variant[v_to]
            row = {"model_id": model_id, "contrast": label}
            for key in a:
                if key == "n_records":
                    continue
                av, bv = a.get(key), b.get(key)
                row[f"{key}_delta"] = round(bv - av, 3) if (av is not None and bv is not None) else None
            delta_rows.append(row)

    variant_fields = ["model_id", "variant", "n_records", "direct_total", "derived_total",
                       "speculative_total", "groundedness_ratio", "speculation_volume_per_record",
                       "direct_per_record"] + [f"mean_score_{d}" for d in (*SCORE_DIMENSIONS, "overall")]
    write_csv(OUT_DIR / "paired_contrasts_by_variant.csv", variant_fields, variant_rows)

    if delta_rows:
        delta_fields = ["model_id", "contrast"] + [k for k in delta_rows[0] if k not in ("model_id", "contrast")]
        write_csv(OUT_DIR / "paired_contrasts_deltas.csv", delta_fields, delta_rows)

    print("\nPaired deltas (positive = higher in the second variant of the pair):")
    for row in delta_rows:
        print(f"\n  {row['model_id']} — {row['contrast']}")
        for key, val in row.items():
            if key in ("model_id", "contrast") or val is None:
                continue
            print(f"    {key:38s} {val:+.3f}" if isinstance(val, float) else f"    {key:38s} {val:+d}")


if __name__ == "__main__":
    main()
