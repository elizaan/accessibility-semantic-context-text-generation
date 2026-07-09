"""
Value fidelity — for every DIRECT and DERIVED claim (SPECULATIVE excluded
on purpose: those never claim to be grounded in the data in the first
place, so "does this number match the table" isn't a meaningful question
for them), extract the numbers inside that specific claim and check them
against the chart's REAL data table — the ground truth we (the
evaluators) always have access to, regardless of whether it was actually
in the prompt the model received.

Scope: restricted to charts that actually HAVE a real data_table in
metadata (checked once per chart, applied across every variant for that
chart — including V3/V4, where the table wasn't in the prompt but we
still have it). Charts with no table at all are dropped entirely, not
kept around in a separate "unscoreable" bucket.

Every number-like token gets assessed — no magnitude-based noise filter.
Whole numbers, decimals, percentages, and x/y fractions are all in scope;
there's no assumption here about which numbers are "real claims" versus
years/positions/anything else.

Two ground-truth pools per chart, built once from chart.metadata.data_table
and cached (see _ground_truth_pools):

  raw_pool      every numeric cell value in the table.
  derived_pool  every plausible simple computation over pairs of values in
                the same column: differences, percent changes, ratios (as
                both raw and as a %), plus per-column sum/mean/min/max.
                This is a heuristic plausibility check, not a semantic
                one — it doesn't know which two rows a DERIVED claim is
                actually comparing, so it checks whether the claimed
                number matches *any* simple computation that could
                plausibly have produced it.

DIRECT claims are checked against raw_pool only (a DIRECT claim is
supposed to be verbatim, so "matches some derived computation but not any
raw cell" is itself informative, not a pass). DERIVED claims are checked
against raw_pool UNION derived_pool, since a legitimate derived claim is
expected to be a computed value, not a copied one.

This is still pattern matching, not a verified re-derivation of the
model's actual reasoning — a match means "a real ground-truth quantity
exists that equals this number," not "the model definitely computed it
correctly the way it says it did." Treat it as a strong candidate signal,
same caveat as everywhere else in this package.

Reports accuracy by (model, variant, flag_kind) — including V3/V4, where
every claim is *unauthorized* by construction (see provenance_audit.py)
but can still be checked for whether it happens to be *accurate*: is a
model fabricating plausible numbers or wild ones when it has nothing to
go on?

Usage (from backend/): python -m evaluation.value_fidelity
"""

from __future__ import annotations

import csv as csv_module
import io
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, split_into_flagged_claims, write_csv

REPORT_DIR = OUT_DIR / "report"
REPORT_DIR.mkdir(exist_ok=True)

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Olli's chart.metadata.data_table is empty for all 7 charts in this
# project, but their vega_lite_spec references real external datasets from
# the public vega-datasets repo (the standard Vega/Vega-Lite example-data
# source) instead of embedding values inline — checked directly against
# each chart's actual spec before writing this, not assumed. One chart
# (olli_choropleth-map) references only US county boundary TopoJSON
# geometry with no joined numeric values — genuinely nothing to check
# there, so it stays excluded. The rest are fetched once and cached to
# disk (CACHE_DIR) so re-running this script doesn't depend on network
# access or on vega-datasets staying at these exact URLs forever.
OLLI_EXTERNAL_DATASETS: dict[str, tuple[str, str]] = {
    "olli_faceted-chart": ("json", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/barley.json"),
    "olli_stacked-bar-chart": ("json", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/barley.json"),
    "olli_heatmap": ("csv", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/seattle-weather.csv"),
    "olli_population-pyramid": ("json", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/population.json"),
    "olli_scatterplot": ("json", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/penguins.json"),
    "olli_streamgraph": ("json", "https://raw.githubusercontent.com/vega/vega-datasets/next/data/unemployment-across-industries.json"),
    # olli_choropleth-map deliberately omitted — geometry only, no values.
}


def _fetch_external_dataset(chart_id: str) -> list[dict] | None:
    if chart_id not in OLLI_EXTERNAL_DATASETS:
        return None
    fmt, url = OLLI_EXTERNAL_DATASETS[chart_id]
    cache_path = CACHE_DIR / f"{chart_id}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    print(f"[value_fidelity] fetching external dataset for {chart_id}: {url}")
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read().decode("utf-8")

    if fmt == "json":
        rows = json.loads(raw)
    else:  # csv
        rows = list(csv_module.DictReader(io.StringIO(raw)))
        # DictReader gives every value as a string — let _parse_numeric_value
        # (already handles numeric-looking strings) sort out which ones are.

    cache_path.write_text(json.dumps(rows))
    return rows

# Two alternatives: comma-grouped thousands (1,234 / 12,345,678), or a
# plain digit run of any length (2020, 45000). \d{1,3}(?:,\d{3})* alone
# (an earlier version of this pattern) silently truncates plain 4+ digit
# numbers with no comma to their first 3 digits — "2018" -> "201" — which
# is exactly how years and any uncommified data value were getting
# corrupted into garbage values before being checked against ground truth.
#
# Leading (?<![\d\w]) blocks the sign from attaching when immediately
# preceded by a digit OR a letter — the digit case stops a hyphenated
# range ("20-25%", "2023-2025") from being misread as 20 and -25 (a
# negative number that was actually the second half of a range); the
# letter case stops a hyphenated compound name directly touching a number
# ("COVID-19", "Type-2") from being misread as the negative number -19 or
# -2, which isn't a data value at all — it's part of a name.
# Sign class includes the Unicode minus (U+2212, "−") alongside ASCII "-" —
# a couple of generated outputs use it too, and the real data (see
# _parse_numeric_value) uses it routinely.
NUMBER_PATTERN = re.compile(r"(?<![\d\w])[-−+]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")

# x/y fractions ("1/2", "3/4") — a separate pattern since NUMBER_PATTERN
# would otherwise match the two sides as unrelated numbers.
FRACTION_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")

# Word-Number compounds with no space ("COVID-19", "Type-2", "G-7") — once
# the sign can't attach (see above), the bare digits ("19", "2") would
# still match NUMBER_PATTERN as if they were real values. Excluded by the
# same span-overlap mechanism as fractions and L-level labels below.
_COMPOUND_WORD_NUMBER_PATTERN = re.compile(r"(?<=[A-Za-z])[-−]\d+")

# "L1".."L4" — this benchmark's own caption-level labels (see prompts.yaml),
# not a chart data value. Excluded by name, not by magnitude: this is a
# specific, known token this project itself defines, unlike the old
# blanket "small numbers are probably noise" filter that got removed.
_LEVEL_LABEL_PATTERN = re.compile(r"(?<=[Ll])[1-4](?!\d)")

# Word-based magnitude multipliers ("12 million") — found by hand-checking
# a real claim: "ranging from 0 to over 12 million" was extracted as the
# bare value 12.0 and checked against a pool of raw people-counts like
# 11,234,567, comparing at completely the wrong scale. Immediately after a
# NUMBER_PATTERN match only, so "12 million dollars" scales but something
# like "the 12th million-dollar deal" (multiplier not adjacent) doesn't.
_MULTIPLIER_WORDS: dict[str, float] = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_MULTIPLIER_SUFFIX_PATTERN = re.compile(r"^\s*(thousand|million|billion)\b", re.IGNORECASE)

FLAG_KINDS_CHECKED = ("direct", "derived")


def _parse_number(token: str) -> tuple[float, bool] | tuple[None, None]:
    """Returns (value, is_percent) or (None, None) if not parseable."""
    is_percent = token.endswith("%")
    cleaned = token.replace("$", "").replace(",", "").replace("%", "").replace("−", "-")
    try:
        return float(cleaned), is_percent
    except ValueError:
        return None, None


def _extract_numbers(text: str) -> list[tuple[float, bool, float]]:
    """
    Every number-like token gets assessed — no magnitude-based noise
    filter. An earlier version dropped bare small integers on the
    assumption they were years/positions/L-levels rather than real
    claims; that's exactly the kind of unverified assumption that isn't
    trustworthy in a fabrication check, so it's gone. Whole numbers,
    decimals, percentages, and x/y fractions are all extracted — with
    four narrow, verified exclusions (not magnitude-based assumptions):
    season/date notation ("2005/06") isn't a fraction, a hyphenated range
    ("20-25%") isn't a negative number, "COVID-19"-style compound names
    aren't negative numbers either, and this project's own "L1".."L4"
    caption-level labels aren't chart data.

    Returns (value, is_percent, word_multiplier) — word_multiplier is 1
    unless the number is immediately followed by "thousand"/"million"/
    "billion", in which case it's that word's scale factor. The caller
    tries BOTH the literal value and value*word_multiplier against the
    pool, never just one: found by hand-checking that some charts store
    already-scaled values matching their own title ("(in millions)"
    literally storing 3.0 for 3 million), while others store raw values
    that need the multiplier applied to match a word-based claim like "12
    million". Picking one scale deterministically breaks the other case.
    """
    out = []
    fraction_spans: list[tuple[int, int]] = []
    for match in FRACTION_PATTERN.finditer(text):
        num, denom = int(match.group(1)), int(match.group(2))
        # "2005/06"-style season notation, not a fraction.
        if 1900 <= num <= 2099:
            continue
        if denom != 0:
            out.append((num / denom, False, 1.0))
            fraction_spans.append(match.span())

    excluded_spans = list(fraction_spans)
    for m in _LEVEL_LABEL_PATTERN.finditer(text):
        excluded_spans.append(m.span())
    for m in _COMPOUND_WORD_NUMBER_PATTERN.finditer(text):
        excluded_spans.append(m.span())

    for match in NUMBER_PATTERN.finditer(text):
        if any(s <= match.start() < e or s < match.end() <= e for s, e in excluded_spans):
            continue
        token = match.group()
        value, is_percent = _parse_number(token)
        if value is None:
            continue
        mult = _MULTIPLIER_SUFFIX_PATTERN.match(text[match.end():match.end() + 12])
        multiplier = _MULTIPLIER_WORDS[mult.group(1).lower()] if mult else 1.0
        out.append((value, is_percent, multiplier))
    return out


def _parse_numeric_value(v) -> float | None:
    """
    Handles real int/float cells AND numeric-looking strings — 22 of the
    36 charts with a data_table store at least one numeric column as a
    string (e.g. '−0.1872', '66.0346'), several using the Unicode minus
    sign (U+2212) rather than ASCII '-'. An earlier version only accepted
    isinstance(v, (int, float)), which silently dropped every one of
    those values from the ground truth pool — undercounting "correct"
    across most of the dataset, not a minor gap.
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.strip().replace("−", "-").replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _numeric_columns(data_table: list[dict]) -> dict[str, list[float]]:
    cols: dict[str, list[float]] = defaultdict(list)
    for row in data_table:
        for k, v in row.items():
            parsed = _parse_numeric_value(v)
            if parsed is not None:
                cols[k].append(parsed)
    return cols


# Targeted check for claims like "67 observations fall between 5000 and
# 6300 g" — a real, verified-correct example (67/344 penguins, checked by
# hand against the real dataset) got marked "fabricated" because it's a
# computed count, and no operation in _ground_truth_pools's derived_pool
# covers "count of rows in a range." Rather than precomputing every
# possible range in advance (intractable — ranges are unbounded), this
# parses the claim's OWN stated boundaries and count, then computes the
# real count directly. Narrow and pattern-specific by design, not a
# general NLP range parser — it catches this one claim shape.
_RANGE_COUNT_PATTERN = re.compile(
    r"(\d[\d,]*)\s+(?:\w+\s+){0,2}?"
    r"(?:observations?|values?|points?|rows?|entries|counties|regions?|countries?|records?|cases?)"
    r"[^.]{0,40}?between\s+([\d,]+(?:\.\d+)?)\s+and\s+([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _verify_range_counts(claim_text: str, data_table: list[dict] | None) -> set[float]:
    """
    Returns the set of claimed counts in claim_text that check out as
    correct against at least one numeric column of the real data_table.
    Only the count itself is verified this way — the range boundaries
    (5000, 6300 in the example) are descriptive bucket edges the model
    chose, not claims about a specific real data point, and are left to
    the normal pool check, where they're expected not to match.
    """
    verified: set[float] = set()
    if not data_table:
        return verified
    for m in _RANGE_COUNT_PATTERN.finditer(claim_text):
        try:
            claimed = float(m.group(1).replace(",", ""))
            lo = float(m.group(2).replace(",", ""))
            hi = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        if lo > hi:
            lo, hi = hi, lo
        for values in _numeric_columns(data_table).values():
            real_count = sum(1 for v in values if lo <= v <= hi)
            # +-1 tolerance for inclusive/exclusive boundary ambiguity —
            # "between 5000 and 6300" doesn't specify whether the
            # endpoints themselves count.
            if abs(real_count - claimed) <= 1:
                verified.add(claimed)
                break
    return verified


def _extract_scene_graph_text(node) -> list[str]:
    """
    Pulls every rendered text-mark string out of a Vega scene graph —
    these are the axis tick labels and title actually printed on the
    chart. Checked: no "datum" field anywhere in this project's vistext
    scene graphs, so there's no per-mark data value to recover, only what
    the axes literally show. Still useful — e.g. vistext_31's data_table
    only covers 2015-2019, but the scene graph's x-axis tick labels show
    2015-2025 (2020-2025 marked with "*", i.e. projected), which is real
    evidence the chart legitimately displays those years even though the
    table doesn't confirm per-year values for them.
    """
    out: list[str] = []
    if isinstance(node, dict):
        if node.get("marktype") == "text":
            for item in node.get("items", []) or []:
                if isinstance(item, dict) and "text" in item:
                    t = item["text"]
                    if isinstance(t, list):
                        out.extend(str(x) for x in t)
                    else:
                        out.append(str(t))
        for v in node.values():
            out.extend(_extract_scene_graph_text(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_extract_scene_graph_text(v))
    return out


_pool_cache: dict[str, tuple[set[float], set[float], set[float]]] = {}


def _ground_truth_pools(
    chart_id: str, data_table: list[dict] | None, scene_graph: dict | None, olli_tree: str | None = None
) -> tuple[set[float], set[float], set[float]]:
    """Returns (raw_pool, derived_pool, axis_pool), cached per chart_id —
    the pools don't depend on model/variant, only on the chart's real data.

    axis_pool is kept SEPARATE from raw_pool on purpose: it's built from
    scene_graph axis tick labels (gridline scale markers, e.g. "-0.20",
    "-0.15" ... "0.00"), not confirmed per-category data points. A claim
    matching an axis tick means "this number is within the chart's
    visible scale," not "this is a real data value for a specific
    category" — those are different strengths of evidence and reported as
    a separate verdict tier, not folded into "correct."

    olli_tree numbers (avg/min/max/count per group, e.g. "Avg rate: 0.09")
    go into derived_pool, not raw_pool — they're real, but they're
    aggregate statistics Olli computed, not a single literal per-record
    cell, which is the same epistemic status as this project's own
    computed pairwise quantities. This is olli_choropleth-map's ONLY
    ground truth source (it has no data_table and its vega_lite_spec
    references only county-boundary geometry, no joined values) — without
    it, that chart would have nothing to check against at all.
    """
    if chart_id in _pool_cache:
        return _pool_cache[chart_id]

    raw_pool: set[float] = set()
    derived_pool: set[float] = set()
    axis_pool: set[float] = set()

    if olli_tree:
        for value, _is_percent, _mult in _extract_numbers(olli_tree):
            derived_pool.add(round(value, 2))

    if data_table:
        for values in _numeric_columns(data_table).values():
            for v in values:
                raw_pool.add(round(v, 2))
            if len(values) >= 2:
                derived_pool.update({round(sum(values), 2), round(sum(values) / len(values), 2),
                                      round(min(values), 2), round(max(values), 2)})
            for i in range(len(values)):
                for j in range(i + 1, len(values)):
                    a, b = values[i], values[j]
                    derived_pool.add(round(b - a, 2))
                    derived_pool.add(round(a - b, 2))
                    if a != 0:
                        derived_pool.add(round((b - a) / abs(a) * 100, 2))
                        derived_pool.add(round(b / a, 2))
                        derived_pool.add(round(b / a * 100, 2))
                    if b != 0:
                        derived_pool.add(round((a - b) / abs(b) * 100, 2))
                        derived_pool.add(round(a / b, 2))
                        derived_pool.add(round(a / b * 100, 2))

    if scene_graph:
        for text in _extract_scene_graph_text(scene_graph):
            v = _parse_numeric_value(text)
            if v is not None:
                axis_pool.add(round(v, 2))

    _pool_cache[chart_id] = (raw_pool, derived_pool, axis_pool)
    return raw_pool, derived_pool, axis_pool


def _matches(value: float, pool: set[float], tolerance_abs: float = 0.5, tolerance_rel: float = 0.02) -> bool:
    if not pool:
        return False
    tol = max(tolerance_abs, abs(value) * tolerance_rel)
    return any(abs(value - t) <= tol for t in pool)


def _title_indicates_thousands(title: str | None) -> bool:
    if not title:
        return False
    t = title.lower()
    return "1,000s" in t or "in thousands" in t


def _matches_scaled(
    value: float, is_percent: bool, pool: set[float], thousands_ok: bool = False, word_multiplier: float = 1.0
) -> bool:
    """
    Checks a claim's value against the pool at its literal scale, plus
    evidence-gated rescalings — not a blind sweep of every plausible
    factor, which a systematic scan showed produces far more coincidental
    noise than real signal (e.g. "19" from "19 age values," a count,
    spuriously matching an unrelated real value near 1900):

      is_percent      claim written as a percent ("63%", parsed as 63.0)
                      is also checked /100, since data tables routinely
                      store a share as a 0-1 fraction (0.63). Found by
                      hand-checking: vistext_4's table has 'Share of
                      respondents': 0.63; a claim of "selected by 63%"
                      was scoring "fabricated" purely from this mismatch.

      thousands_ok    only set when the chart's own title says
                      "(in 1,000s)" (see _title_indicates_thousands) — a
                      claim is also checked /1000, since prose sometimes
                      spells out the full number ("156,670 members")
                      while the table stores the pre-divided value
                      (156.67) the title promised.

      word_multiplier from _extract_numbers — 1000/1e6/1e9 if the claim
                      said "thousand"/"million"/"billion", else 1. Tried
                      as value*word_multiplier, ALONGSIDE the literal
                      value, never instead of it: some charts store raw
                      values (need the multiplier to match "12 million"),
                      others store already-scaled values matching their
                      own title, e.g. vistext_7 "(in millions)" literally
                      stores 3.0 for 3 million — multiplying would break
                      that case. An earlier version of this fix always
                      multiplied and silently turned some previously-
                      correct verdicts into false "fabricated" ones for
                      exactly that chart; checking both scales fixes it
                      without reintroducing the original problem.
    """
    if _matches(value, pool):
        return True
    if is_percent and _matches(value / 100, pool):
        return True
    if thousands_ok and _matches(value / 1000, pool):
        return True
    if word_multiplier != 1.0 and _matches(value * word_multiplier, pool):
        return True
    return False


_resolved_table_cache: dict[str, list[dict] | None] = {}


def _resolve_data_table(chart) -> list[dict] | None:
    """Native data_table if present; otherwise the fetched external
    vega-datasets table for the Olli charts that have one (see
    OLLI_EXTERNAL_DATASETS); otherwise None."""
    if chart.chart_id in _resolved_table_cache:
        return _resolved_table_cache[chart.chart_id]
    table = chart.metadata.data_table or _fetch_external_dataset(chart.chart_id)
    _resolved_table_cache[chart.chart_id] = table
    return table


def main() -> None:
    all_records = [r for r in load_records() if r.parse_ok]

    # Scope restriction: only charts with a real, resolvable ground truth
    # source — native chart.metadata.data_table, (for 6 of 7 Olli charts)
    # the external vega-datasets table their vega_lite_spec references, or
    # (for all 7 Olli charts, including the choropleth map that has
    # neither of the above) the olli_tree accessible-summary text, which
    # contains real aggregate statistics (avg/min/max/count per group).
    # Applied at the chart level, across every variant for that chart
    # (including V3/V4, where the ground truth wasn't in the prompt but we
    # still have it as evaluators). Charts with nothing at all are dropped
    # entirely rather than kept around in an "unscoreable" bucket.
    chart_ids_with_table = {
        r.chart_id for r in all_records
        if r.chart and (_resolve_data_table(r.chart) or r.chart.metadata.olli_tree)
    }
    records = [r for r in all_records if r.chart_id in chart_ids_with_table]
    n_charts_total = len({r.chart_id for r in all_records})
    print(f"[value_fidelity] scope: {len(chart_ids_with_table)}/{n_charts_total} charts have a "
          f"resolvable ground truth source — restricting to those: {sorted(chart_ids_with_table)}")

    claim_rows = []
    # (model_id, variant, flag_kind) -> counts
    summary: dict[tuple[str, int, str], dict[str, int]] = defaultdict(
        lambda: {"n_numbers": 0, "correct": 0, "matches_axis_label": 0, "fabricated": 0}
    )

    for r in records:
        data_table = _resolve_data_table(r.chart)
        scene_graph = r.chart.metadata.scene_graph
        olli_tree = r.chart.metadata.olli_tree
        raw_pool, derived_pool, axis_pool = _ground_truth_pools(r.chart_id, data_table, scene_graph, olli_tree)
        thousands_ok = _title_indicates_thousands(r.chart.title)

        for section in SECTION_KEYS:
            text = r.sections.get(section, "")
            if not text:
                continue
            for kind, claim_text in split_into_flagged_claims(text):
                if kind not in FLAG_KINDS_CHECKED:
                    continue

                numbers = _extract_numbers(claim_text)
                if not numbers:
                    continue

                range_verified_counts = _verify_range_counts(claim_text, data_table)

                key = (r.model_id, r.variant, kind)
                for value, is_percent, word_multiplier in numbers:
                    summary[key]["n_numbers"] += 1

                    check_pool = raw_pool if kind == "direct" else (raw_pool | derived_pool)
                    if value in range_verified_counts:
                        # A computed count ("67 observations between 5000
                        # and 6300g") verified directly against the real
                        # table — not a pool lookup, see _verify_range_counts.
                        verdict = "correct"
                        summary[key]["correct"] += 1
                    elif _matches_scaled(value, is_percent, check_pool, thousands_ok, word_multiplier):
                        verdict = "correct"
                        summary[key]["correct"] += 1
                    elif _matches_scaled(value, is_percent, axis_pool, thousands_ok, word_multiplier):
                        # Matches a real axis tick/gridline label — visibly
                        # on the chart, but a scale marker, not a confirmed
                        # per-category data point. Weaker than "correct",
                        # much stronger than unmatched.
                        verdict = "matches_axis_label"
                        summary[key]["matches_axis_label"] += 1
                    else:
                        verdict = "fabricated"
                        summary[key]["fabricated"] += 1

                    claim_rows.append({
                        "chart_id": r.chart_id,
                        "model_id": r.model_id,
                        "variant": r.variant,
                        "section": section,
                        "flag_kind": kind,
                        "extracted_value": value,
                        "is_percent": is_percent,
                        "verdict": verdict,
                        "claim_text": claim_text.strip()[-160:],
                    })

    write_csv(
        OUT_DIR / "value_fidelity_claims.csv",
        ["chart_id", "model_id", "variant", "section", "flag_kind", "extracted_value",
         "is_percent", "verdict", "claim_text"],
        claim_rows,
    )

    summary_rows = []
    for (model_id, variant, kind), counts in sorted(summary.items()):
        n = counts["n_numbers"]
        summary_rows.append({
            "model_id": model_id,
            "variant": variant,
            "flag_kind": kind,
            "n_numbers": n,
            "n_correct": counts["correct"],
            "n_matches_axis_label": counts["matches_axis_label"],
            "n_fabricated": counts["fabricated"],
            "accuracy_pct": round(100 * counts["correct"] / n, 1) if n else "",
        })
    write_csv(
        OUT_DIR / "value_fidelity_summary.csv",
        ["model_id", "variant", "flag_kind", "n_numbers", "n_correct", "n_matches_axis_label",
         "n_fabricated", "accuracy_pct"],
        summary_rows,
    )

    # ── markdown table ───────────────────────────────────────────────────
    md_lines = [f"# Value Fidelity — DIRECT/DERIVED numeric claims vs. real ground truth\n",
                f"Scope: only the {len(chart_ids_with_table)}/{n_charts_total} charts with a "
                f"resolvable data table (native data_table, or for 6 of 7 Olli charts, the external "
                f"vega-datasets table their vega_lite_spec references), every variant. "
                f"accuracy_pct = share of extracted numbers that match "
                f"the real data table (raw cells for DIRECT; raw cells + simple computed quantities "
                f"for DERIVED) or a scene_graph axis tick label. SPECULATIVE claims excluded — they "
                f"don't claim grounding. Checked even in V3/V4, where the model never saw the table "
                f"but we still know the truth. No noise filter — every number-like token (whole "
                f"numbers, decimals, percentages, x/y fractions) is assessed, regardless of "
                f"magnitude. n_matches_axis_label is a separate, weaker tier: matches a real value "
                f"visible on the chart's axis (scene_graph, vistext only), not a confirmed "
                f"per-category data point — not counted toward accuracy_pct.\n",
                "| model_id | variant | flag_kind | n_numbers | n_correct | n_matches_axis_label | n_fabricated | accuracy_pct |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in summary_rows:
        if row["n_numbers"]:
            md_lines.append(f"| {row['model_id']} | {row['variant']} | {row['flag_kind']} | "
                             f"{row['n_numbers']} | {row['n_correct']} | {row['n_matches_axis_label']} | "
                             f"{row['n_fabricated']} | "
                             f"{row['accuracy_pct']} |")
    (REPORT_DIR / "value_fidelity_table.md").write_text("\n".join(md_lines) + "\n")
    print(f"[value_fidelity] wrote {REPORT_DIR / 'value_fidelity_table.md'}")

    # ── plot: accuracy_pct by variant, one panel per flag_kind, grouped by model ──
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
                ys.append(match["accuracy_pct"] if match and match["accuracy_pct"] != "" else 0)
            xs = [vi + i * width for vi in range(len(variants))]
            ax.bar(xs, ys, width=width, label=model.split("/")[-1])
        ax.set_xticks([vi + width * (len(models) - 1) / 2 for vi in range(len(variants))])
        ax.set_xticklabels([f"V{v}" for v in variants])
        ax.set_title(f"{kind.upper()} claims")
        ax.set_xlabel("Variant")
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("Accuracy vs. real ground truth (%)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Numeric claim accuracy — DIRECT vs DERIVED, checked against real data table")
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "value_fidelity_accuracy.png", dpi=150)
    plt.close(fig)
    print(f"[value_fidelity] wrote {REPORT_DIR / 'value_fidelity_accuracy.png'}")

    print("\nAccuracy vs. real ground truth, by model x variant x flag kind "
          "(only charts with a data table; SPECULATIVE excluded):")
    for row in summary_rows:
        if row["n_numbers"]:
            print(f"  {row['model_id']:38s} V{row['variant']} {row['flag_kind']:8s} "
                  f"n={row['n_numbers']:>4d} correct={row['n_correct']:>4d} "
                  f"axis_label={row['n_matches_axis_label']:>3d} "
                  f"accuracy={row['accuracy_pct']}%")


if __name__ == "__main__":
    main()
