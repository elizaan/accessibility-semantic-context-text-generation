"""
Side-by-side check for value_fidelity.py's regex-based number matching:
does a claim's TEXT (not just the numbers extracted from it) semantically
match something in the chart's real ground truth, using a real text
embedding model (OpenAI text-embedding-3-small)?

This is a genuinely different method, not a refinement of the regex one —
run them side by side, don't read one as correcting the other:

  value_fidelity.py            checks whether a specific extracted number
                                equals a specific real quantity (exact,
                                tolerance-based, blind to phrasing).
  value_fidelity_embedding.py  checks whether a claim's overall MEANING is
                                close to some real statement about the
                                chart (robust to paraphrasing/rounding,
                                blind to whether the specific number is
                                actually correct).

A claim could pass one and fail the other — that's not a bug, that's the
two methods measuring different things.

Ground truth verbalization per chart (cached, built once):
  - one sentence per data table row.
  - a SMALLER set of derived-comparison sentences than value_fidelity.py's
    exhaustive all-pairs pool: consecutive-row deltas, first-vs-last, and
    column aggregates (sum/mean/min/max) only. Embedding every pairwise
    combination the way the free numeric pool does would mean thousands
    of extra API calls per large table for a check that's supposed to be
    a couple hours of scripting — this is a deliberately narrower
    ground-truth set, not an oversight.

For every DIRECT/DERIVED claim span (same claims, same chart scope as
value_fidelity.py — only charts with a real data_table), embeds the claim
text and finds its best cosine-similarity match among that chart's
ground-truth sentences. Reports MEAN best-similarity per (model, variant,
flag_kind) as a continuous score — no fixed "correct" threshold is
applied, since there's no established cutoff for this task; a binary rate
at a chosen threshold is a follow-up decision, not baked in here.

Costs real OpenAI API calls (existing OPENAI_API_KEY) — cheap given the
volume here (a few thousand short texts, batched), but not free like the
rest of this package.

Usage (from backend/): python -m evaluation.value_fidelity_embedding
"""

from __future__ import annotations

import math
from collections import defaultdict

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, split_into_flagged_claims, write_csv
from evaluation.value_fidelity import FLAG_KINDS_CHECKED, _numeric_columns

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 500


def _verbalize_row(row: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in row.items())


def _verbalize_ground_truth(data_table: list[dict]) -> list[str]:
    sentences = [_verbalize_row(row) for row in data_table]

    for col, values in _numeric_columns(data_table).items():
        if len(values) < 2:
            continue
        for i in range(len(values) - 1):
            a, b = values[i], values[i + 1]
            diff = b - a
            s = f"For '{col}', consecutive values changed from {a} to {b}, a difference of {diff:.2f}"
            if a != 0:
                s += f" ({diff / abs(a) * 100:.1f}%)"
            sentences.append(s)
        a, b = values[0], values[-1]
        sentences.append(f"For '{col}', from the first value ({a}) to the last value ({b}), "
                          f"a difference of {b - a:.2f}")
        sentences.append(f"For '{col}', sum={sum(values):.2f}, mean={sum(values) / len(values):.2f}, "
                          f"min={min(values):.2f}, max={max(values):.2f}")
    return sentences


_embed_cache: dict[str, list[float]] = {}


def _embed_all(texts: list[str]) -> None:
    """Embeds every unique text not already cached, batched."""
    from app.core.config import settings
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    uncached = sorted({t for t in texts if t and t not in _embed_cache})
    if not uncached:
        return
    for i in range(0, len(uncached), BATCH_SIZE):
        batch = uncached[i:i + BATCH_SIZE]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        for t, d in zip(batch, resp.data):
            _embed_cache[t] = d.embedding
        print(f"[value_fidelity_embedding] embedded {min(i + BATCH_SIZE, len(uncached))}/{len(uncached)}")


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def main() -> None:
    all_records = [r for r in load_records() if r.parse_ok]
    chart_ids_with_table = {
        r.chart_id for r in all_records if r.chart and r.chart.metadata.data_table
    }
    records = [r for r in all_records if r.chart_id in chart_ids_with_table]
    n_charts_total = len({r.chart_id for r in all_records})
    print(f"[value_fidelity_embedding] scope: {len(chart_ids_with_table)}/{n_charts_total} charts "
          f"have a real data_table — same scope as value_fidelity.py")

    # ── ground truth sentences per chart ────────────────────────────────
    gt_sentences_by_chart: dict[str, list[str]] = {}
    for r in records:
        if r.chart_id not in gt_sentences_by_chart:
            gt_sentences_by_chart[r.chart_id] = _verbalize_ground_truth(r.chart.metadata.data_table)

    # ── claim spans (same unit as value_fidelity.py's claims, but one
    # embedding per claim SPAN, not one per extracted number within it) ──
    claim_entries = []
    for r in records:
        for section in SECTION_KEYS:
            text = r.sections.get(section, "")
            if not text:
                continue
            for kind, claim_text in split_into_flagged_claims(text):
                if kind not in FLAG_KINDS_CHECKED or not claim_text.strip():
                    continue
                claim_entries.append((r, section, kind, claim_text.strip()))

    all_gt_texts = [s for sents in gt_sentences_by_chart.values() for s in sents]
    claim_texts = [c[3] for c in claim_entries]
    print(f"[value_fidelity_embedding] {len(set(all_gt_texts))} unique ground-truth sentences, "
          f"{len(set(claim_texts))} unique claim texts to embed")
    _embed_all(all_gt_texts)
    _embed_all(claim_texts)

    gt_vecs_by_chart = {
        cid: [_embed_cache[s] for s in sents if s in _embed_cache]
        for cid, sents in gt_sentences_by_chart.items()
    }

    claim_rows = []
    summary: dict[tuple[str, int, str], list[float]] = defaultdict(list)

    for r, section, kind, claim_text in claim_entries:
        if claim_text not in _embed_cache:
            continue
        claim_vec = _embed_cache[claim_text]
        gt_vecs = gt_vecs_by_chart.get(r.chart_id, [])
        if not gt_vecs:
            continue
        best_sim = max(_cosine(claim_vec, gv) for gv in gt_vecs)

        key = (r.model_id, r.variant, kind)
        summary[key].append(best_sim)
        claim_rows.append({
            "chart_id": r.chart_id,
            "model_id": r.model_id,
            "variant": r.variant,
            "section": section,
            "flag_kind": kind,
            "best_similarity": round(best_sim, 4),
            "claim_text": claim_text[-200:],
        })

    write_csv(
        OUT_DIR / "value_fidelity_embedding_claims.csv",
        ["chart_id", "model_id", "variant", "section", "flag_kind", "best_similarity", "claim_text"],
        claim_rows,
    )

    summary_rows = []
    for (model_id, variant, kind), sims in sorted(summary.items()):
        n = len(sims)
        summary_rows.append({
            "model_id": model_id,
            "variant": variant,
            "flag_kind": kind,
            "n_claims": n,
            "mean_similarity": round(sum(sims) / n, 4) if n else "",
            "min_similarity": round(min(sims), 4) if sims else "",
            "max_similarity": round(max(sims), 4) if sims else "",
        })
    write_csv(
        OUT_DIR / "value_fidelity_embedding_summary.csv",
        ["model_id", "variant", "flag_kind", "n_claims", "mean_similarity", "min_similarity", "max_similarity"],
        summary_rows,
    )

    # ── plot: mean similarity by variant, one panel per flag_kind, grouped by model ──
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = sorted({r["model_id"] for r in summary_rows})
    variants = sorted({r["variant"] for r in summary_rows})

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, kind in zip(axes, FLAG_KINDS_CHECKED):
        width = 0.8 / len(models)
        for i, model in enumerate(models):
            ys = []
            for v in variants:
                match = next((r for r in summary_rows
                              if r["model_id"] == model and r["variant"] == v and r["flag_kind"] == kind), None)
                ys.append(match["mean_similarity"] if match and match["mean_similarity"] != "" else 0)
            xs = [vi + i * width for vi in range(len(variants))]
            ax.bar(xs, ys, width=width, label=model.split("/")[-1])
        ax.set_xticks([vi + width * (len(models) - 1) / 2 for vi in range(len(variants))])
        ax.set_xticklabels([f"V{v}" for v in variants])
        ax.set_title(f"{kind.upper()} claims")
        ax.set_xlabel("Variant")
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("Mean cosine similarity to real ground truth")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Semantic grounding ({EMBED_MODEL}) — DIRECT vs DERIVED claims vs. real data table")
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "value_fidelity_embedding.png", dpi=150)
    plt.close(fig)
    print(f"[value_fidelity_embedding] wrote {REPORT_DIR / 'value_fidelity_embedding.png'}")

    print("\nMean semantic similarity to real ground truth, by model x variant x flag kind:")
    for row in summary_rows:
        print(f"  {row['model_id']:38s} V{row['variant']} {row['flag_kind']:8s} "
              f"n={row['n_claims']:>4d} mean_sim={row['mean_similarity']}")


if __name__ == "__main__":
    main()
