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

import argparse
import csv as csv_module
import io
import json
import random
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.common import OUT_DIR, SECTION_KEYS, load_records, split_into_flagged_claims, write_csv
from evaluation.provenance_audit import _cohens_kappa

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


def _extract_number_matches(text: str) -> list[tuple[float, bool, float, tuple[int, int]]]:
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

    Returns (value, is_percent, word_multiplier, span) — word_multiplier is
    1 unless the number is immediately followed by "thousand"/"million"/
    "billion", in which case it's that word's scale factor. The caller
    tries BOTH the literal value and value*word_multiplier against the
    pool, never just one: found by hand-checking that some charts store
    already-scaled values matching their own title ("(in millions)"
    literally storing 3.0 for 3 million), while others store raw values
    that need the multiplier applied to match a word-based claim like "12
    million". Picking one scale deterministically breaks the other case.

    span is the match's (start, end) character offset in `text` — used by
    the category-matching logic (see _find_category_mention) to find which
    category name, if any, this specific number is closest to, when a
    claim mentions more than one.
    """
    out = []
    fraction_spans: list[tuple[int, int]] = []
    for match in FRACTION_PATTERN.finditer(text):
        num, denom = int(match.group(1)), int(match.group(2))
        # "2005/06"-style season notation, not a fraction.
        if 1900 <= num <= 2099:
            continue
        if denom != 0:
            out.append((num / denom, False, 1.0, match.span()))
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
        out.append((value, is_percent, multiplier, match.span()))
    return out


def _extract_numbers(text: str) -> list[tuple[float, bool, float]]:
    """Thin wrapper over _extract_number_matches for the many call sites
    that only need (value, is_percent, word_multiplier), not the span."""
    return [(v, p, m) for v, p, m, _span in _extract_number_matches(text)]


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


# Tuple verification (category + series + value, not just "value exists
# somewhere") — additive on top of the flat-pool check above, not a
# replacement, following the same precedent as axis_pool being layered in
# as a separate, weaker tier rather than folded into "correct". A claim
# saying "Group A is 15%" should only be tuple-verified if Group A's own
# real row actually has 15% — the flat-pool check alone would also call it
# "correct" if 15% belongs to a completely different entity.
_CATEGORY_KEY_ALLOWLIST = ("entity", "response", "variety", "year", "country", "name", "category", "group", "label")


def _category_column(data_table: list[dict]) -> str | None:
    """
    Identifies which column holds the row's category/entity name, so a
    claim's number can be checked against the SPECIFIC row it's about, not
    just the table as a whole. Tries known key names first (case
    insensitive) — "Entity" is by far the most common in this project's
    OWID-sourced charts. Falls back to the first key that's non-numeric in
    at least 90% of rows (a real category column has a few stray blank/odd
    cells sometimes, but shouldn't be mostly numeric). Returns None rather
    than guessing if nothing qualifies — some tables (e.g. a single-row
    snapshot with all-numeric columns) genuinely have no category to check
    against, and this function says so rather than picking an arbitrary key.
    """
    if not data_table:
        return None
    keys = list(data_table[0].keys())
    lower_keys = {k.lower(): k for k in keys}
    for allowed in _CATEGORY_KEY_ALLOWLIST:
        if allowed in lower_keys:
            return lower_keys[allowed]

    for key in keys:
        n_rows = len(data_table)
        n_numeric = sum(1 for row in data_table if _parse_numeric_value(row.get(key)) is not None)
        if n_rows and (n_rows - n_numeric) / n_rows >= 0.9:
            return key
    return None


def _find_category_mention(
    claim_text: str, number_span: tuple[int, int], category_values: list[str]
) -> str | None:
    """
    Searches claim_text (case-insensitive, exact-or-substring — no
    entity-alias table, e.g. "US" won't match "United States"; a known,
    documented limitation that makes this check conservative rather than
    over-permissive) for any of the chart's real category values. If more
    than one appears in the same claim (e.g. an explicit two-entity
    comparison), picks whichever is closest in character position to the
    number's own match span, since that's the value the number is most
    likely actually describing.
    """
    claim_lower = claim_text.lower()
    num_start, num_end = number_span
    best: tuple[int, str] | None = None
    for cat in category_values:
        cat_lower = str(cat).strip().lower()
        if not cat_lower or len(cat_lower) < 2:
            continue
        idx = 0
        while True:
            pos = claim_lower.find(cat_lower, idx)
            if pos == -1:
                break
            distance = min(abs(pos - num_end), abs((pos + len(cat_lower)) - num_start))
            if best is None or distance < best[0]:
                best = (distance, cat)
            idx = pos + 1
    return best[1] if best else None


# Direction words for simple two-entity comparison claims ("X rose from...
# to...", "A is higher than B"). Narrow and pattern-specific by design,
# like _RANGE_COUNT_PATTERN above — not a general trend-direction parser,
# and deliberately NOT applied to single-entity time-trend claims (too
# easy to misattribute which two points are being compared).
_INCREASE_WORDS = ("rose", "rising", "grew", "growing", "increased", "increasing", "up", "higher", "gained", "climbed")
_DECREASE_WORDS = ("fell", "falling", "dropped", "dropping", "declined", "declining", "down", "lower", "lost", "shrank")


def _claimed_direction(claim_text: str) -> str | None:
    claim_lower = claim_text.lower()
    has_increase = any(re.search(rf"\b{w}\b", claim_lower) for w in _INCREASE_WORDS)
    has_decrease = any(re.search(rf"\b{w}\b", claim_lower) for w in _DECREASE_WORDS)
    if has_increase and not has_decrease:
        return "increase"
    if has_decrease and not has_increase:
        return "decrease"
    return None


def _category_row_column_match(
    data_table: list[dict], category_col: str, category_value: str,
    value: float, is_percent: bool, thousands_ok: bool, word_multiplier: float,
) -> str | None:
    """Returns the name of the first numeric column where category_value's
    OWN row reproduces `value` (via the same _matches_scaled tolerance
    used everywhere else), or None if no column in that specific row does.
    This is the actual tuple check: not "does 15% appear anywhere in the
    table" but "does Group A's own row contain 15% in some column"."""
    for row in data_table:
        if str(row.get(category_col)).strip().lower() != str(category_value).strip().lower():
            continue
        for col, v in row.items():
            if col == category_col:
                continue
            parsed = _parse_numeric_value(v)
            if parsed is None:
                continue
            if _matches_scaled(value, is_percent, {round(parsed, 2)}, thousands_ok, word_multiplier):
                return col
    return None


# Requires an explicit "from ... to ..." construction so which mention is
# the baseline vs. the comparison point is unambiguous from word order
# alone — deliberately conservative; claims phrased other ways ("A is
# higher than B") just get direction_matched="n-a" rather than a guess.
_FROM_TO_PATTERN = re.compile(r"\bfrom\b(.{1,60}?)\bto\b(.{1,60}?)(?:[.,;]|$)", re.IGNORECASE)


def _category_in_text(text: str, category_values: list[str]) -> str | None:
    text_lower = text.lower()
    best: tuple[int, str] | None = None
    for cat in category_values:
        cat_lower = str(cat).strip().lower()
        if not cat_lower or len(cat_lower) < 2:
            continue
        pos = text_lower.find(cat_lower)
        if pos != -1 and (best is None or pos < best[0]):
            best = (pos, cat)
    return best[1] if best else None


def _row_value(data_table: list[dict], category_col: str, category_value: str, column: str) -> float | None:
    for row in data_table:
        if str(row.get(category_col)).strip().lower() == str(category_value).strip().lower():
            return _parse_numeric_value(row.get(column))
    return None


def _check_direction(
    claim_text: str, data_table: list[dict] | None, category_col: str | None,
    category_values: list[str], verified_column: str | None,
) -> tuple[str | None, str]:
    """Returns (direction_claimed, direction_matched). Only resolves to
    yes/no when: a direction word is present, the claim uses an explicit
    "from X to Y" construction, X and Y each resolve to a distinct real
    category, AND a numeric column was already tuple-verified for this
    claim (so we know which column the comparison is about) — every other
    case is direction_matched="n-a", not a guess."""
    claimed_dir = _claimed_direction(claim_text)
    if claimed_dir is None or not verified_column or not data_table or not category_col:
        return claimed_dir, "n-a"
    m = _FROM_TO_PATTERN.search(claim_text)
    if not m:
        return claimed_dir, "n-a"
    cat_a = _category_in_text(m.group(1), category_values)
    cat_b = _category_in_text(m.group(2), category_values)
    if not cat_a or not cat_b or cat_a == cat_b:
        return claimed_dir, "n-a"
    val_a = _row_value(data_table, category_col, cat_a, verified_column)
    val_b = _row_value(data_table, category_col, cat_b, verified_column)
    if val_a is None or val_b is None or val_a == val_b:
        return claimed_dir, "n-a"
    real_dir = "increase" if val_b > val_a else "decrease"
    return claimed_dir, ("yes" if real_dir == claimed_dir else "no")


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


def run_automated() -> None:
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
        lambda: {"n_numbers": 0, "correct": 0, "matches_axis_label": 0, "fabricated": 0, "tuple_verified": 0}
    )

    for r in records:
        data_table = _resolve_data_table(r.chart)
        scene_graph = r.chart.metadata.scene_graph
        olli_tree = r.chart.metadata.olli_tree
        raw_pool, derived_pool, axis_pool = _ground_truth_pools(r.chart_id, data_table, scene_graph, olli_tree)
        thousands_ok = _title_indicates_thousands(r.chart.title)

        category_col = _category_column(data_table) if data_table else None
        category_values = (
            sorted({str(row.get(category_col)) for row in data_table if row.get(category_col) is not None})
            if category_col else []
        )

        for section in SECTION_KEYS:
            text = r.sections.get(section, "")
            if not text:
                continue
            for kind, claim_text in split_into_flagged_claims(text):
                if kind not in FLAG_KINDS_CHECKED:
                    continue

                number_matches = _extract_number_matches(claim_text)
                if not number_matches:
                    continue

                range_verified_counts = _verify_range_counts(claim_text, data_table)

                key = (r.model_id, r.variant, kind)
                for value, is_percent, word_multiplier, span in number_matches:
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

                    # ── Tuple verification: does the SPECIFIC category this
                    # claim names actually have this value, not just "does
                    # this value exist somewhere in the table" — additive,
                    # doesn't change `verdict` above. Only meaningful when
                    # verdict=="correct" and a category column exists.
                    verified_column = None
                    if not category_col:
                        category_matched = "n-a"
                        tuple_verified = "not_applicable"
                    else:
                        mentioned = _find_category_mention(claim_text, span, category_values)
                        if not mentioned:
                            category_matched = "no_category_mentioned"
                            tuple_verified = "not_applicable"
                        else:
                            category_matched = "yes"
                            if verdict != "correct":
                                tuple_verified = "not_applicable"
                            else:
                                verified_column = _category_row_column_match(
                                    data_table, category_col, mentioned, value, is_percent, thousands_ok, word_multiplier
                                )
                                tuple_verified = "yes" if verified_column else "no"
                                if tuple_verified == "yes":
                                    summary[key]["tuple_verified"] += 1

                    direction_claimed, direction_matched = _check_direction(
                        claim_text, data_table, category_col, category_values, verified_column
                    )

                    claim_rows.append({
                        "chart_id": r.chart_id,
                        "model_id": r.model_id,
                        "variant": r.variant,
                        "section": section,
                        "flag_kind": kind,
                        "extracted_value": value,
                        "is_percent": is_percent,
                        "verdict": verdict,
                        "category_matched": category_matched,
                        "tuple_verified": tuple_verified,
                        "direction_claimed": direction_claimed or "none",
                        "direction_matched": direction_matched,
                        "claim_text": claim_text.strip()[-160:],
                    })

    write_csv(
        OUT_DIR / "value_fidelity_claims.csv",
        ["chart_id", "model_id", "variant", "section", "flag_kind", "extracted_value",
         "is_percent", "verdict", "category_matched", "tuple_verified", "direction_claimed",
         "direction_matched", "claim_text"],
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
            "n_tuple_verified": counts["tuple_verified"],
            "tuple_verified_pct": round(100 * counts["tuple_verified"] / counts["correct"], 1) if counts["correct"] else "",
        })
    write_csv(
        OUT_DIR / "value_fidelity_summary.csv",
        ["model_id", "variant", "flag_kind", "n_numbers", "n_correct", "n_matches_axis_label",
         "n_fabricated", "accuracy_pct", "n_tuple_verified", "tuple_verified_pct"],
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
                  f"accuracy={row['accuracy_pct']}% "
                  f"tuple_verified={row['n_tuple_verified']:>4d} ({row['tuple_verified_pct']}% of correct)")


# ── sample: stratified claim sample for a two-annotator human audit of the
# checker itself, to estimate its own false-positive/false-negative rate —
# same shape of problem as provenance_audit.py's sample/score, deliberately
# kept in this file rather than split into a new one, matching how
# provenance_audit.py already keeps automated+sample+score together for
# the same class of task. ──────────────────────────────────────────────────

def run_sample(cap_per_stratum: int = 30, seed: int = 0) -> None:
    """
    Stratifies by (model_id, verdict) — verdict in {correct, fabricated,
    matches_axis_label} — rather than provenance_audit.py's flat 12%-of-
    everything fraction, because this audit's whole purpose is estimating
    a false-positive rate (within "correct") and a false-negative rate
    (within "fabricated") PER MODEL, and accuracy already varies a lot by
    model (see value_fidelity_summary.csv) — a flat fraction would make
    the "correct" stratum tiny for a weaker model while making
    "fabricated" unmanageably large for it. Caps each stratum at
    `cap_per_stratum` claims instead (default 30, confirmed with the
    project owner) rather than sampling every claim in a small stratum.

    Requires value_fidelity_claims.csv to already exist (run `automated`
    first) — reads it back rather than recomputing, so the sample reflects
    exactly what was actually verdicted, and re-running this command is
    cheap (no ground-truth pool rebuilding, no network fetches).
    """
    claims_path = OUT_DIR / "value_fidelity_claims.csv"
    if not claims_path.exists():
        raise SystemExit(f"[value_fidelity] {claims_path} doesn't exist yet — run "
                          f"`python -m evaluation.value_fidelity automated` first.")
    with claims_path.open(newline="", encoding="utf-8") as f:
        all_claims = list(csv_module.DictReader(f))

    # Re-join chart/model/variant -> full claim_text (un-truncated) and
    # real chart data, since the bulk claims CSV truncates claim_text to
    # its last 160 chars for readability — an annotator needs the whole
    # claim, and critically the real row the checker matched against.
    records_by_key = {(r.chart_id, r.model_id, r.variant): r for r in load_records() if r.parse_ok}

    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in all_claims:
        strata[(row["model_id"], row["verdict"])].append(row)

    sample_rows = []
    sample_id = 0
    for (model_id, verdict), pool in sorted(strata.items()):
        chosen = rng.sample(pool, min(cap_per_stratum, len(pool)))
        for row in chosen:
            sample_id += 1
            key = (row["chart_id"], row["model_id"], int(row["variant"]))
            record = records_by_key.get(key)
            chart = record.chart if record else None

            # Full, un-truncated claim text — re-derive from the section
            # text rather than trusting the truncated CSV column.
            claim_text_full = row["claim_text"]
            if record:
                text = record.sections.get(row["section"], "")
                for kind, ct in split_into_flagged_claims(text):
                    if kind == row["flag_kind"] and row["claim_text"] in ct:
                        claim_text_full = ct.strip()
                        break

            matched_category_row = ""
            data_table_preview = ""
            if chart:
                data_table = _resolve_data_table(chart)
                category_col = _category_column(data_table) if data_table else None
                if row["category_matched"] == "yes" and data_table and category_col:
                    span = (0, 0)  # only used for tie-breaking among multiple mentions; fine to re-derive loosely here
                    category_values = sorted({str(r.get(category_col)) for r in data_table if r.get(category_col) is not None})
                    mentioned = _find_category_mention(claim_text_full, span, category_values)
                    if mentioned:
                        for dt_row in data_table:
                            if str(dt_row.get(category_col)).strip().lower() == mentioned.strip().lower():
                                matched_category_row = str(dt_row)
                                break
                if not matched_category_row and data_table:
                    data_table_preview = str(data_table[:5])
                    if len(data_table) > 5:
                        data_table_preview += f" … ({len(data_table)} rows total)"

            sample_rows.append({
                "sample_id": sample_id,
                "chart_id": row["chart_id"],
                "model_id": row["model_id"],
                "variant": row["variant"],
                "chart_title": chart.title if chart else "",
                "extracted_value": row["extracted_value"],
                "is_percent": row["is_percent"],
                "verdict": row["verdict"],
                "category_matched": row["category_matched"],
                "tuple_verified": row["tuple_verified"],
                "direction_claimed": row["direction_claimed"],
                "direction_matched": row["direction_matched"],
                "matched_category_row": matched_category_row,
                "data_table_columns": str(list(chart.metadata.data_table[0].keys())) if chart and chart.metadata.data_table else "",
                "data_table_preview": data_table_preview,
                "claim_text": claim_text_full,
                "annotator1_valid": "",
                "annotator2_valid": "",
                "notes": "",
            })

    fieldnames = ["sample_id", "chart_id", "model_id", "variant", "chart_title", "extracted_value",
                  "is_percent", "verdict", "category_matched", "tuple_verified", "direction_claimed",
                  "direction_matched", "matched_category_row", "data_table_columns", "data_table_preview",
                  "claim_text", "annotator1_valid", "annotator2_valid", "notes"]
    write_csv(OUT_DIR / "value_fidelity_audit_sample.csv", fieldnames, sample_rows)
    print(f"\n{len(sample_rows)} claims sampled (cap {cap_per_stratum}/stratum) across {len(strata)} "
          f"(model, verdict) strata.")
    print("Fill in annotator1_valid / annotator2_valid with valid/invalid/unsure per row — judging whether "
          "the model's stated NUMBER is actually correct, independent of what `verdict` already says — then run:")
    print("  python -m evaluation.value_fidelity score evaluation/out/value_fidelity_audit_sample.csv")


def run_score(path: str) -> None:
    """
    False-positive rate: among sampled verdict=="correct" rows, the
    fraction where both annotators agree the claim is actually "invalid".
    False-negative rate: among sampled verdict=="fabricated" rows, the
    fraction where both annotators agree the claim is actually "valid".
    Both rates also recomputed restricted to tuple_verified=="yes" vs.
    not, reported side by side — the direct, quantified answer to "did
    the tuple-verification upgrade actually help."
    """
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv_module.DictReader(f))

    both_rated = [r for r in rows if r["annotator1_valid"].strip() and r["annotator2_valid"].strip()]
    if not both_rated:
        print("No rows have both annotator1_valid and annotator2_valid filled in yet — nothing to score.")
        return

    r1 = [r["annotator1_valid"].strip().lower() for r in both_rated]
    r2 = [r["annotator2_valid"].strip().lower() for r in both_rated]
    kappa = _cohens_kappa(r1, r2)
    print(f"Cohen's kappa ({len(both_rated)} double-annotated claims): {kappa:.3f}" if kappa is not None else "n/a")

    def _rate(subset: list[dict], verdict: str, agreed_label: str) -> tuple[int, int, float | None]:
        pool = [r for r in subset if r["verdict"] == verdict]
        n = len(pool)
        agreed = sum(
            1 for r in pool
            if r["annotator1_valid"].strip().lower() == agreed_label
            and r["annotator2_valid"].strip().lower() == agreed_label
        )
        return agreed, n, round(agreed / n, 3) if n else None

    fp_agreed, fp_n, fp_rate = _rate(both_rated, "correct", "invalid")
    fn_agreed, fn_n, fn_rate = _rate(both_rated, "fabricated", "valid")

    tuple_yes = [r for r in both_rated if r["tuple_verified"] == "yes"]
    tuple_not_yes = [r for r in both_rated if r["tuple_verified"] != "yes"]
    fp_tv_agreed, fp_tv_n, fp_tv_rate = _rate(tuple_yes, "correct", "invalid")
    fp_ntv_agreed, fp_ntv_n, fp_ntv_rate = _rate(tuple_not_yes, "correct", "invalid")

    print(f"\nFalse-positive rate (verdict=correct but both annotators say invalid): "
          f"{fp_agreed}/{fp_n} = {fp_rate}")
    print(f"False-negative rate (verdict=fabricated but both annotators say valid): "
          f"{fn_agreed}/{fn_n} = {fn_rate}")
    print(f"\n  ...restricted to tuple_verified=='yes':     {fp_tv_agreed}/{fp_tv_n} = {fp_tv_rate}")
    print(f"  ...restricted to tuple_verified!='yes':     {fp_ntv_agreed}/{fp_ntv_n} = {fp_ntv_rate}")

    result_rows = [{
        "n_double_annotated": len(both_rated),
        "cohens_kappa": round(kappa, 3) if kappa is not None else "",
        "false_positive_agreed": fp_agreed, "false_positive_n": fp_n, "false_positive_rate": fp_rate,
        "false_negative_agreed": fn_agreed, "false_negative_n": fn_n, "false_negative_rate": fn_rate,
        "fp_rate_tuple_verified_yes": fp_tv_rate, "fp_n_tuple_verified_yes": fp_tv_n,
        "fp_rate_tuple_verified_not_yes": fp_ntv_rate, "fp_n_tuple_verified_not_yes": fp_ntv_n,
    }]
    write_csv(
        OUT_DIR / "value_fidelity_scored_audit.csv",
        list(result_rows[0].keys()),
        result_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("automated", help="Run the automated numeric-fidelity check (writes value_fidelity_claims.csv).")

    p_sample = sub.add_parser("sample", help="Generate a stratified claim sample for human annotation.")
    p_sample.add_argument("--cap", type=int, default=30, dest="cap_per_stratum")
    p_sample.add_argument("--seed", type=int, default=0)

    p_score = sub.add_parser("score", help="Score a completed annotation sample.")
    p_score.add_argument("path")

    args = parser.parse_args()
    if args.command == "automated":
        run_automated()
    elif args.command == "sample":
        run_sample(args.cap_per_stratum, args.seed)
    elif args.command == "score":
        run_score(args.path)


if __name__ == "__main__":
    main()
