"""
Provenance validity audit — the credibility core of this evaluation.

Self-reported flags are not proof of groundedness (see this project's own
flag-taxonomy discussion: a model rationalizes a claim as DIRECT/DERIVED
because it *feels* grounded, it doesn't introspect on whether it actually
is). This script has two parts:

  automated   Free, no-annotation signal: in V3/V4, no metadata was ever
              provided, so any [DIRECT] claim is a misattribution by
              construction. CAVEAT, important: every V3 record currently
              on disk was generated *before* the chart_title leak fix
              (prompt_service.py used to show the real title even in V3).
              So this reports both a raw rate (every V3 DIRECT claim
              counted) and a title-adjusted rate (claims that plausibly
              reference the chart's title excluded, via substring/word-
              overlap heuristic) — the adjusted number is the fairer one
              for existing data; re-running V3 generations after the fix
              would make the raw and adjusted numbers converge.

  sample/score  The real human audit: `sample` draws a stratified ~12% of
              claims across (model, variant) into a CSV with full
              reference context (title, data table preview, captions,
              domain/stakeholder context) so two annotators can judge each
              claim without switching back to the app. `score` reads the
              completed CSV back and reports Cohen's kappa plus per-model
              misattribution rate.

Usage (from backend/):
  python -m evaluation.provenance_audit automated
  python -m evaluation.provenance_audit sample [--fraction 0.12] [--seed 0]
  python -m evaluation.provenance_audit score <path-to-completed-sample.csv>
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from collections import Counter, defaultdict

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, write_csv

_WORD_RE = re.compile(r"[a-z]{3,}")


def _title_overlap(claim: str, title: str | None) -> bool:
    if not title:
        return False
    claim_l, title_l = claim.lower(), title.lower()
    if title_l in claim_l:
        return True
    title_words = set(_WORD_RE.findall(title_l))
    claim_words = set(_WORD_RE.findall(claim_l))
    if not title_words:
        return False
    return len(title_words & claim_words) / len(title_words) >= 0.6


# ── automated: any DIRECT claim in V3/V4 is a misattribution ───────────────

def run_automated() -> None:
    records = [r for r in load_records() if r.parse_ok and r.variant in (3, 4)]

    rows = []
    grouped: dict[tuple[str, int], list] = defaultdict(list)
    for r in records:
        grouped[(r.model_id, r.variant)].append(r)

    for (model_id, variant), recs in sorted(grouped.items()):
        n_direct = sum(len(r.direct_claims) for r in recs)
        n_raw = n_direct  # every DIRECT claim, no adjustment
        n_adjusted = 0
        n_title_excluded = 0
        for r in recs:
            for claim in r.direct_claims:
                if variant == 3 and _title_overlap(claim, r.chart_title):
                    n_title_excluded += 1
                else:
                    n_adjusted += 1

        rows.append({
            "model_id": model_id,
            "variant": variant,
            "n_records": len(recs),
            "n_direct_claims": n_direct,
            "n_title_excluded": n_title_excluded,
            "n_misattributed_adjusted": n_adjusted,
            "misattribution_rate_raw": round(n_raw / (n_direct or 1), 3) if n_direct else "",
            "misattribution_rate_adjusted": round(n_adjusted / (n_direct or 1), 3) if n_direct else "",
        })

    write_csv(
        OUT_DIR / "provenance_automated_v3v4.csv",
        ["model_id", "variant", "n_records", "n_direct_claims", "n_title_excluded",
         "n_misattributed_adjusted", "misattribution_rate_raw", "misattribution_rate_adjusted"],
        rows,
    )

    print("\nAutomated V3/V4 misattribution (any [DIRECT] claim with no metadata provided):")
    for row in rows:
        print(f"  {row['model_id']:38s} V{row['variant']} "
              f"direct_claims={row['n_direct_claims']:>4d} "
              f"title_excluded={row['n_title_excluded']:>3d} "
              f"raw_rate={row['misattribution_rate_raw']} "
              f"adjusted_rate={row['misattribution_rate_adjusted']}")


# ── sample: stratified claim sample for two-annotator human audit ──────────

def _section_for_claim(claim: str, sections: dict[str, str]) -> str:
    for key in SECTION_KEYS:
        if claim and claim in sections.get(key, ""):
            return key
    return "unmatched"


def _reference_context(r) -> dict[str, str]:
    chart = r.chart
    meta = chart.metadata if chart else None
    table_preview = ""
    if meta and meta.data_table:
        table_preview = str(meta.data_table[:5])
        if len(meta.data_table) > 5:
            table_preview += f" … ({len(meta.data_table)} rows total)"
    return {
        "chart_title": chart.title or "" if chart else "",
        "data_table_preview": table_preview,
        "alt_text": (meta.alt_text or "") if meta else "",
        "domain_context": (meta.domain_context or "") if meta else "",
        "stakeholder_context": (meta.stakeholder_context or "") if meta else "",
        "l1_caption": (meta.l1_caption or "") if meta else "",
        "l2_caption": (meta.l2_caption or "") if meta else "",
        "l3_caption": (meta.l3_caption or "") if meta else "",
    }


def run_sample(fraction: float, seed: int) -> None:
    records = [r for r in load_records() if r.parse_ok]
    rng = random.Random(seed)

    # Stratify by (model, variant); within each stratum, pool every
    # individual claim (flag_type-tagged) and sample `fraction` of them.
    strata: dict[tuple[str, int], list[tuple]] = defaultdict(list)
    for r in records:
        for flag_type, claims in (
            ("DIRECT", r.direct_claims),
            ("DERIVED", r.derived_claims),
            ("SPECULATIVE", r.speculative_claims),
        ):
            for claim in claims:
                strata[(r.model_id, r.variant)].append((r, flag_type, claim))

    rows = []
    sample_id = 0
    for key, pool in sorted(strata.items()):
        n_sample = max(1, round(len(pool) * fraction)) if pool else 0
        chosen = rng.sample(pool, min(n_sample, len(pool)))
        for r, flag_type, claim in chosen:
            sample_id += 1
            ctx = _reference_context(r)
            rows.append({
                "sample_id": sample_id,
                "chart_id": r.chart_id,
                "model_id": r.model_id,
                "variant": r.variant,
                "flag_type": flag_type,
                "claim_text": claim,
                "section": _section_for_claim(claim, r.sections),
                **ctx,
                "annotator1_valid": "",
                "annotator2_valid": "",
                "notes": "",
            })

    fieldnames = ["sample_id", "chart_id", "model_id", "variant", "flag_type", "claim_text", "section",
                  "chart_title", "data_table_preview", "alt_text", "domain_context", "stakeholder_context",
                  "l1_caption", "l2_caption", "l3_caption", "annotator1_valid", "annotator2_valid", "notes"]
    write_csv(OUT_DIR / "provenance_audit_sample.csv", fieldnames, rows)
    print(f"\n{len(rows)} claims sampled ({fraction:.0%} target) across {len(strata)} (model, variant) strata.")
    print("Fill in annotator1_valid / annotator2_valid with valid/invalid/unsure per row, then run:")
    print("  python -m evaluation.provenance_audit score evaluation/out/provenance_audit_sample.csv")


# ── score: read back a completed sample and compute kappa + misattribution ─

def _cohens_kappa(rater1: list[str], rater2: list[str]) -> float | None:
    n = len(rater1)
    if n == 0:
        return None
    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n
    cats = set(rater1) | set(rater2)
    pe = sum((rater1.count(c) / n) * (rater2.count(c) / n) for c in cats)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def run_score(path: str) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    both_rated = [r for r in rows if r["annotator1_valid"].strip() and r["annotator2_valid"].strip()]
    if not both_rated:
        print("No rows have both annotator1_valid and annotator2_valid filled in yet — nothing to score.")
        return

    r1 = [r["annotator1_valid"].strip().lower() for r in both_rated]
    r2 = [r["annotator2_valid"].strip().lower() for r in both_rated]
    kappa = _cohens_kappa(r1, r2)
    print(f"Cohen's kappa ({len(both_rated)} double-annotated claims): {kappa:.3f}" if kappa is not None else "n/a")

    # Per-model misattribution rate for DIRECT claims specifically — "valid"
    # requires both annotators to agree it's valid; anything else (either
    # marked invalid, or disagreement) counts as a misattribution for this
    # purpose, since disagreement on a DIRECT claim's validity is itself a
    # signal the claim isn't cleanly grounded.
    by_model: dict[str, Counter] = defaultdict(Counter)
    for row in both_rated:
        if row["flag_type"] != "DIRECT":
            continue
        both_valid = row["annotator1_valid"].strip().lower() == "valid" and row["annotator2_valid"].strip().lower() == "valid"
        by_model[row["model_id"]]["total"] += 1
        by_model[row["model_id"]]["valid"] += int(both_valid)

    print("\nPer-model DIRECT-claim misattribution rate (sampled, human-verified):")
    result_rows = []
    for model_id, counts in sorted(by_model.items()):
        total = counts["total"]
        misattributed = total - counts["valid"]
        rate = round(misattributed / total, 3) if total else None
        print(f"  {model_id:38s} {misattributed}/{total} misattributed ({rate})")
        result_rows.append({"model_id": model_id, "n_direct_sampled": total,
                             "n_misattributed": misattributed, "misattribution_rate": rate})

    write_csv(OUT_DIR / "provenance_scored_misattribution.csv",
              ["model_id", "n_direct_sampled", "n_misattributed", "misattribution_rate"], result_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("automated", help="Compute the automated V3/V4 DIRECT-flag misattribution signal.")

    p_sample = sub.add_parser("sample", help="Generate a stratified claim sample for human annotation.")
    p_sample.add_argument("--fraction", type=float, default=0.12)
    p_sample.add_argument("--seed", type=int, default=0)

    p_score = sub.add_parser("score", help="Score a completed annotation sample.")
    p_score.add_argument("path")

    args = parser.parse_args()
    if args.command == "automated":
        run_automated()
    elif args.command == "sample":
        run_sample(args.fraction, args.seed)
    elif args.command == "score":
        run_score(args.path)


if __name__ == "__main__":
    main()
