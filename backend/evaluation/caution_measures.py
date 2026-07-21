"""
Direct measurement of the RQ3 construct (missing-context disclosure ->
does the model behave more cautiously?), instead of only the proxies
(output length, claim volume) the rest of this package otherwise relies
on. Predefined, regex/keyword-based marker categories — not ML-based,
consistent with every other pattern-matching check in this package
(INLINE_FLAG_PATTERN, NUMBER_PATTERN, etc.) — counted per record across
all 4 sections:

  hedging       explicit uncertainty language ("it is unclear", "may
                indicate", "seems to"...) — the model expressing doubt
                about its own claim, short of outright refusing it.

  abstention    explicit refusal/inability to answer ("cannot provide",
                "insufficient information", "cannot be verified"...) — a
                stronger signal than hedging: the model declines to make
                a claim at all rather than making a hedged one.

  missing_info_request   the model explicitly asking for more than it
                was given ("would require", "additional data would be
                needed"...) — distinct from abstention because it names
                what's missing rather than just declining.

  unsupported_causal     causal connective words/phrases ("because", "due
                to", "as a result of", "leads to", "causes", "caused by",
                "driven by", "results in") found specifically INSIDE a
                claim span the model itself already tagged SPECULATIVE
                (via split_into_flagged_claims) — a proxy for "causal
                language not backed by DIRECT/DERIVED evidence," not a
                general causal-language detector. Two explicit failure
                directions, same as every other heuristic in this
                package: undercounts if a model mislabels a causal claim
                as DIRECT/DERIVED instead of SPECULATIVE; blind to causal
                phrasing outside this fixed word list.

None of these categories are mutually exclusive with each other or with
the DIRECT/DERIVED/SPECULATIVE flag taxonomy — a single sentence can be
both hedged AND unsupported-causal, and both get counted.

Usage (from backend/): python -m evaluation.caution_measures
"""

from __future__ import annotations

import re
from collections import defaultdict

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, split_into_flagged_claims, word_count, write_csv

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)

# Phrase-level, not bare-adverb, to reduce noise from incidental word usage
# (e.g. a bare "seems" match-count would also fire on unrelated sentences
# that happen to use the word loosely; "seems to" is closer to the actual
# hedge construction).
_HEDGING_PHRASES = [
    "it is unclear", "it is not clear", "it's unclear", "it's not clear",
    "may indicate", "may suggest", "might suggest", "might indicate",
    "could reflect", "could indicate", "it appears that", "appears to",
    "seems to", "seem to", "cannot be determined", "can not be determined",
    "hard to say", "difficult to say", "likely reflects", "possibly reflects",
]

_ABSTENTION_PHRASES = [
    "cannot provide", "can not provide", "unable to determine",
    "insufficient information", "not enough information",
    "no data available to", "cannot be verified", "can not be verified",
    "this cannot be confirmed", "this can not be confirmed",
    "without the underlying data", "cannot be confirmed from",
]

_MISSING_INFO_PHRASES = [
    "would require", "would need", "additional data would be needed",
    "without further context", "more information is needed",
    "if provided with", "would be needed to", "further data would be",
]

_CAUSAL_CONNECTIVES = [
    "because", "due to", "as a result of", "leads to", "lead to",
    "causes", "caused by", "driven by", "results in", "resulting in",
]


def _count_phrase_hits(text_lower: str, phrases: list[str]) -> int:
    return sum(text_lower.count(p) for p in phrases)


def count_markers(record) -> dict[str, int]:
    """Per-record marker counts across all 4 sections. `record` is an
    evaluation.common.EvalRecord (or anything with the same .sections and
    .parse_ok-guaranteed-populated shape)."""
    full_text = " ".join(record.sections.get(k, "") for k in SECTION_KEYS)
    text_lower = full_text.lower()

    hedging = _count_phrase_hits(text_lower, _HEDGING_PHRASES)
    abstention = _count_phrase_hits(text_lower, _ABSTENTION_PHRASES)
    missing_info = _count_phrase_hits(text_lower, _MISSING_INFO_PHRASES)

    unsupported_causal = 0
    for section in SECTION_KEYS:
        text = record.sections.get(section, "")
        if not text:
            continue
        for kind, claim_text in split_into_flagged_claims(text):
            if kind != "speculative":
                continue
            claim_lower = claim_text.lower()
            unsupported_causal += sum(1 for c in _CAUSAL_CONNECTIVES if c in claim_lower)

    return {
        "hedging": hedging,
        "abstention": abstention,
        "missing_info_request": missing_info,
        "unsupported_causal": unsupported_causal,
    }


def main() -> None:
    records = [r for r in load_records() if r.parse_ok]

    record_rows = []
    # (model_id, variant) -> list of per-record total marker counts + word counts
    by_model_variant: dict[tuple[str, int], list[tuple[dict, int]]] = defaultdict(list)

    for r in records:
        counts = count_markers(r)
        wc = word_count(" ".join(r.sections.get(k, "") for k in SECTION_KEYS))
        total = sum(counts.values())
        record_rows.append({
            "chart_id": r.chart_id,
            "model_id": r.model_id,
            "variant": r.variant,
            "word_count": wc,
            "hedging": counts["hedging"],
            "abstention": counts["abstention"],
            "missing_info_request": counts["missing_info_request"],
            "unsupported_causal": counts["unsupported_causal"],
            "total": total,
            "total_per_100_words": round(100 * total / wc, 3) if wc else "",
        })
        by_model_variant[(r.model_id, r.variant)].append((counts, wc))

    write_csv(
        OUT_DIR / "caution_measures_by_record.csv",
        ["chart_id", "model_id", "variant", "word_count", "hedging", "abstention",
         "missing_info_request", "unsupported_causal", "total", "total_per_100_words"],
        record_rows,
    )

    summary_rows = []
    for (model_id, variant), entries in sorted(by_model_variant.items()):
        n = len(entries)
        sums = {"hedging": 0, "abstention": 0, "missing_info_request": 0, "unsupported_causal": 0}
        total_words = 0
        for counts, wc in entries:
            for k in sums:
                sums[k] += counts[k]
            total_words += wc
        total_markers = sum(sums.values())
        summary_rows.append({
            "model_id": model_id,
            "variant": variant,
            "n_records": n,
            "mean_hedging": round(sums["hedging"] / n, 3),
            "mean_abstention": round(sums["abstention"] / n, 3),
            "mean_missing_info_request": round(sums["missing_info_request"] / n, 3),
            "mean_unsupported_causal": round(sums["unsupported_causal"] / n, 3),
            "total_markers_per_100_words": round(100 * total_markers / total_words, 3) if total_words else "",
        })
    write_csv(
        OUT_DIR / "caution_measures_summary.csv",
        ["model_id", "variant", "n_records", "mean_hedging", "mean_abstention",
         "mean_missing_info_request", "mean_unsupported_causal", "total_markers_per_100_words"],
        summary_rows,
    )

    print("\nCaution/metacognition markers per output, mean by model x variant:")
    for row in summary_rows:
        print(f"  {row['model_id']:38s} V{row['variant']} n={row['n_records']:>4d} "
              f"hedging={row['mean_hedging']:>5} abstention={row['mean_abstention']:>5} "
              f"missing_info={row['mean_missing_info_request']:>5} "
              f"unsupported_causal={row['mean_unsupported_causal']:>5} "
              f"per_100w={row['total_markers_per_100_words']}")


if __name__ == "__main__":
    main()
