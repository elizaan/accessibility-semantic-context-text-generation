"""
L4 fidelity: how well does the generated `real_world_significance` section
track the actual domain story for the chart?

IMPORTANT — ground truth reality check done before writing this: neither
`chart.ground_truth_description.real_world_significance` nor
`chart.metadata.l4_caption` is populated for ANY of the 59 charts currently
generated on (0/59 for both) — vistext's own memory notes call L4 "the gap
to fill," and that gap hasn't been filled yet. What *is* available is
`chart.metadata.domain_context` (the "expert domain story" field used in
V1/V2 prompts), populated for 44/59 charts — every source except vistext
(15 charts, 0 with domain_context). This script uses domain_context as a
proxy ground truth and explicitly reports coverage rather than silently
comparing against nothing; vistext charts are skipped and counted, not
dropped invisibly.

Because L4 is legitimately plural (Lundgard & Satyanarayan's own framing —
multiple valid real-world-significance framings can exist for one chart),
this reports similarity for *scale*, not a pass/fail exact-match, plus
generates a CSV for the human rubric (topically relevant / correct domain /
invented stakes) which is where the real judgment should happen.

Similarity, by default, is a dependency-free bag-of-words TF-IDF cosine —
weaker than a real embedding but adds nothing to requirements.txt. Pass
--use-openai-embeddings to use text-embedding-3-small via the OpenAI API
instead (costs API calls, needs OPENAI_API_KEY) for a stronger signal.

Usage (from backend/):
  python -m evaluation.l4_fidelity
  python -m evaluation.l4_fidelity --use-openai-embeddings
"""

from __future__ import annotations

import argparse
import math
import re
from collections import Counter

from evaluation.common import OUT_DIR, load_records, write_csv

_TOKEN_RE = re.compile(r"[a-z]{3,}")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _build_idf(docs: list[list[str]]) -> dict[str, float]:
    n = len(docs)
    df: Counter[str] = Counter()
    for doc in docs:
        for term in set(doc):
            df[term] += 1
    return {term: math.log((n + 1) / (count + 1)) + 1 for term, count in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    return {term: freq * idf.get(term, 0.0) for term, freq in tf.items()}


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    num = sum(v1[t] * v2[t] for t in common)
    d1 = math.sqrt(sum(v * v for v in v1.values()))
    d2 = math.sqrt(sum(v * v for v in v2.values()))
    if d1 == 0 or d2 == 0:
        return 0.0
    return num / (d1 * d2)


def _openai_embed(texts: list[str]) -> list[list[float]]:
    from app.core.config import settings
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    # Batched — one call for many texts, cheaper and faster than per-text.
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [d.embedding for d in resp.data]


def _vec_cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    d1 = math.sqrt(sum(x * x for x in a))
    d2 = math.sqrt(sum(y * y for y in b))
    return num / (d1 * d2) if d1 and d2 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-openai-embeddings", action="store_true",
                         help="Use text-embedding-3-small via the OpenAI API instead of TF-IDF cosine.")
    args = parser.parse_args()

    records = [r for r in load_records() if r.parse_ok]

    # Ground truth proxy: domain_context. Split by whether it exists.
    scoreable = [r for r in records if r.chart and r.chart.metadata.domain_context]
    no_ground_truth = [r for r in records if not (r.chart and r.chart.metadata.domain_context)]

    charts_scoreable = {r.chart_id for r in scoreable}
    charts_missing = {r.chart_id for r in no_ground_truth}
    print(f"[l4_fidelity] {len(charts_scoreable)} charts have a domain_context proxy ground truth, "
          f"{len(charts_missing)} do not (no L4 signal possible for those): "
          f"{sorted(charts_missing)}")

    generated_texts = [r.sections.get("real_world_significance", "") for r in scoreable]
    ground_truths = [r.chart.metadata.domain_context or "" for r in scoreable]

    if args.use_openai_embeddings:
        print(f"[l4_fidelity] embedding {2 * len(scoreable)} texts via OpenAI text-embedding-3-small…")
        gen_vecs = _openai_embed(generated_texts)
        gt_vecs = _openai_embed(ground_truths)
        similarities = [_vec_cosine(g, t) for g, t in zip(gen_vecs, gt_vecs)]
        method = "openai_text-embedding-3-small"
    else:
        all_docs = [_tokenize(t) for t in generated_texts] + [_tokenize(t) for t in ground_truths]
        idf = _build_idf(all_docs)
        similarities = []
        for gen_text, gt_text in zip(generated_texts, ground_truths):
            gv = _tfidf_vector(_tokenize(gen_text), idf)
            tv = _tfidf_vector(_tokenize(gt_text), idf)
            similarities.append(_cosine(gv, tv))
        method = "tfidf_cosine"

    rows = []
    rubric_rows = []
    for r, sim in zip(scoreable, similarities):
        rows.append({
            "chart_id": r.chart_id,
            "model_id": r.model_id,
            "variant": r.variant,
            "similarity_method": method,
            "similarity": round(sim, 4),
        })
        rubric_rows.append({
            "chart_id": r.chart_id,
            "model_id": r.model_id,
            "variant": r.variant,
            "generated_real_world_significance": r.sections.get("real_world_significance", ""),
            "ground_truth_domain_context": r.chart.metadata.domain_context,
            "topically_relevant": "",
            "correct_domain": "",
            "invented_stakes": "",
            "notes": "",
        })

    write_csv(OUT_DIR / "l4_fidelity_similarity.csv",
              ["chart_id", "model_id", "variant", "similarity_method", "similarity"], rows)
    write_csv(OUT_DIR / "l4_fidelity_human_rubric.csv",
              ["chart_id", "model_id", "variant", "generated_real_world_significance",
               "ground_truth_domain_context", "topically_relevant", "correct_domain",
               "invented_stakes", "notes"], rubric_rows)

    from collections import defaultdict
    by_model_variant: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        by_model_variant[(row["model_id"], row["variant"])].append(row["similarity"])

    print(f"\nL4 fidelity ({method}) — mean similarity to domain_context, "
          f"n={len(charts_scoreable)} charts with ground truth:")
    for (model_id, variant), sims in sorted(by_model_variant.items()):
        print(f"  {model_id:38s} V{variant} n={len(sims):>3d} mean_sim={sum(sims)/len(sims):.3f}")


if __name__ == "__main__":
    main()
