"""
Single-purpose, stdlib-only paired-bootstrap helper.

Given a list of per-chart paired differences (metric(chart, variant_b) -
metric(chart, variant_a), one value per chart that has both variants), this
resamples the DIFFERENCE list itself, with replacement — not the two
underlying variant samples separately — so the by-chart pairing is
preserved automatically in every resample, exactly as it was observed.

Method: percentile bootstrap (2.5th/97.5th percentile of the resampled
means for a 95% CI), not bias-corrected-and-accelerated (BCa). BCa needs a
from-scratch bias-correction (z0) and jackknife-based acceleration
estimate on top of the resampling itself — real extra complexity for a
robustness gain that mainly matters when you're trying to make a precise
population-level inference from a skewed or small-n sample. The charts in
this project were purposively sampled, not drawn at random from a defined
population of charts, so a CI here is already a description of resampling
variability among the charts actually run, not a population estimate —
the added sophistication of BCa would overstate the rigor of what is
fundamentally a descriptive summary. Percentile is simpler, sufficient,
and honest about what it is.

n_resamples=10000 by default: at this project's scale (at most ~100 charts
x 3 models x 3 contrasts x ~9 metric rows), even 10000 resamples per row
costs a small fraction of a second in total — there's no real cost
argument for fewer, and no real precision argument for (many) more given
the underlying n is small either way.

Usage:
    from evaluation.bootstrap import bootstrap_ci
    result = bootstrap_ci([b - a for a, b in pairs])
    # {"n": ..., "mean_diff": ..., "ci_lo": ..., "ci_hi": ...}
"""

from __future__ import annotations

import random


def bootstrap_ci(
    diffs: list[float], n_resamples: int = 10000, seed: int = 0, ci: float = 0.95
) -> dict[str, float | int | None]:
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean_diff": None, "ci_lo": None, "ci_hi": None}

    mean_diff = sum(diffs) / n
    if n == 1:
        # A single pair has no resampling variability to speak of — report
        # the point estimate with no interval, rather than a fabricated
        # zero-width one.
        return {"n": 1, "mean_diff": round(mean_diff, 4), "ci_lo": None, "ci_hi": None}

    rng = random.Random(seed)
    resampled_means = []
    for _ in range(n_resamples):
        resample = [diffs[rng.randrange(n)] for _ in range(n)]
        resampled_means.append(sum(resample) / n)
    resampled_means.sort()

    alpha = (1 - ci) / 2
    lo_idx = int(alpha * n_resamples)
    hi_idx = int((1 - alpha) * n_resamples) - 1
    hi_idx = min(hi_idx, n_resamples - 1)

    return {
        "n": n,
        "mean_diff": round(mean_diff, 4),
        "ci_lo": round(resampled_means[lo_idx], 4),
        "ci_hi": round(resampled_means[hi_idx], 4),
    }
