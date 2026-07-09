"""
Shared data loading for the evaluation scripts.

Joins Chart (ground truth: data_table, captions, domain/stakeholder context,
ground_truth_description) with every GenerationOutput on disk, and normalizes
the two schema eras this project has gone through so far:

  - identification.metadata_completeness had 5 dimensions early on
    (domain_expert_context, stakeholder_impact included), trimmed to 3
    later (data_values, trend_magnitude, chart_subject_domain) because the
    two dropped dimensions were near-binary and uninformative. "overall" is
    always recomputed from whichever of the 3 canonical dimensions are
    present, the same way the frontend does — never trusted from storage.
  - flags used DIRECT/SPECULATIVE/UNVERIFIED before DERIVED existed. In
    practice every stored record already uses DIRECT/DERIVED/SPECULATIVE
    (verified against all 712 files before writing this), so no fallback
    for the older taxonomy was implemented — if you ever see a KeyError
    here on `derived_claims`, that assumption broke and this needs revisiting.

Run scripts as modules from the `backend/` directory, e.g.:
    cd backend && .venv/bin/python -m evaluation.flag_distribution
This lets Python resolve the `evaluation` package itself; this file then
puts `backend/` on sys.path so the `app.*` imports inside it resolve too.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.models.chart import Chart  # noqa: E402
from app.services.dataset_service import get_all_charts  # noqa: E402
from app.services.llm_service import load_outputs_for_chart  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# The three models that have actually been run end-to-end this session.
# Claude has zero stored outputs as of this writing (see session notes) —
# add it here once real Claude data exists.
REQUIRED_MODELS: frozenset[str] = frozenset({
    "gemini-3.5-flash",
    "gpt-5.4",
    "meta-llama/llama-4-scout-17b-16e-instruct",
})

VARIANT_LABELS: dict[int, str] = {
    0: "Custom/Partial",
    1: "Full Metadata + Image",
    2: "Full Metadata, No Image",
    3: "Sparse (Image Only)",
    4: "Withheld Metadata",
}

# The canonical identification dimensions — anything else (the two dropped
# dimensions from the 5-dim era) is ignored everywhere in this package.
SCORE_DIMENSIONS: tuple[str, ...] = ("data_values", "trend_magnitude", "chart_subject_domain")

SECTION_KEYS: tuple[str, ...] = (
    "contextual_insights",
    "domain_specific_explanations",
    "real_world_significance",
    "other",
)

# Same pattern ParsedOutputView.tsx uses to render flag badges. Some models
# (confirmed: gpt-5.4) don't keep flags.speculative_claims etc. verbatim in
# sync with the inline-tagged text — they paraphrase when populating that
# list, which breaks substring matching against it. Counting the inline
# [DIRECT]/[DERIVED]/[SPECULATIVE] tags directly, per section, sidesteps
# that entirely: it's reading the same tags a human reader of the output
# would see, not trying to reconcile two independently-authored lists.
INLINE_FLAG_PATTERN = re.compile(r"\[(DIRECT|DERIVED|SPECULATIVE)(?::[^\]]*)?\]")


def count_inline_flags(text: str) -> dict[str, int]:
    counts = {"direct": 0, "derived": 0, "speculative": 0}
    for match in INLINE_FLAG_PATTERN.finditer(text):
        counts[match.group(1).lower()] += 1
    return counts


def split_into_flagged_claims(text: str) -> list[tuple[str, str]]:
    """
    Splits text into (kind, claim_text) pairs, one per inline flag tag —
    claim_text is everything between the previous tag (or the start of the
    text) and this one, i.e. the claim the tag is actually attached to.
    Lets callers check a number against ground truth only when it's inside
    a DIRECT/DERIVED claim, not anywhere in the section regardless of what
    it was actually flagged as.
    """
    results: list[tuple[str, str]] = []
    last_end = 0
    for match in INLINE_FLAG_PATTERN.finditer(text):
        kind = match.group(1).lower()
        claim_text = text[last_end:match.start()]
        results.append((kind, claim_text))
        last_end = match.end()
    return results


@dataclass
class EvalRecord:
    output_id: str
    chart_id: str
    source: str
    chart_type: str
    domain: str
    chart_title: str | None
    model_id: str
    variant: int
    enabled_features: list[str]
    include_image: bool
    created_at: str
    parse_ok: bool
    section_schema_ok: bool = True  # False if the model returned non-string section(s)
    scores: dict[str, float] = field(default_factory=dict)  # dims + "overall", recomputed
    sections: dict[str, str] = field(default_factory=dict)
    direct_claims: list[str] = field(default_factory=list)
    derived_claims: list[str] = field(default_factory=list)
    speculative_claims: list[str] = field(default_factory=list)
    chart: Chart | None = None

    @property
    def variant_label(self) -> str:
        return VARIANT_LABELS.get(self.variant, f"Unknown ({self.variant})")

    @property
    def total_claims(self) -> int:
        return len(self.direct_claims) + len(self.derived_claims) + len(self.speculative_claims)

    @property
    def groundedness_ratio(self) -> float | None:
        """(DIRECT + DERIVED) / total claims — None if there are no claims at all."""
        total = self.total_claims
        if total == 0:
            return None
        return (len(self.direct_claims) + len(self.derived_claims)) / total


def _recompute_scores(parsed: dict) -> dict[str, float]:
    dims = (
        parsed.get("identification", {})
        .get("metadata_completeness", {})
    )
    scores: dict[str, float] = {}
    for dim in SCORE_DIMENSIONS:
        v = dims.get(dim)
        if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
            scores[dim] = float(v["score"])
    if scores:
        scores["overall"] = sum(scores.values()) / len(scores)
    return scores


def _record_from_output(chart: Chart, raw: dict) -> EvalRecord:
    parsed = raw.get("parsed_output")
    parse_ok = isinstance(parsed, dict)

    scores: dict[str, float] = {}
    sections: dict[str, str] = {}
    direct: list[str] = []
    derived: list[str] = []
    speculative: list[str] = []
    section_schema_ok = True

    if parse_ok:
        scores = _recompute_scores(parsed)
        desc = parsed.get("generated_description", {}) or {}
        for k in SECTION_KEYS:
            v = desc.get(k, "")
            if isinstance(v, str):
                sections[k] = v
            elif isinstance(v, list):
                # Some models occasionally return a list of sentences
                # instead of a single string for a section — a genuine
                # schema-compliance failure worth tracking, not just papering
                # over silently.
                section_schema_ok = False
                sections[k] = " ".join(str(x) for x in v)
            else:
                section_schema_ok = False
                sections[k] = str(v) if v else ""
        flags = parsed.get("flags", {}) or {}
        direct = list(flags.get("direct_claims", []) or [])
        derived = list(flags.get("derived_claims", []) or [])
        speculative = list(flags.get("speculative_claims", []) or [])

    return EvalRecord(
        output_id=raw["output_id"],
        chart_id=raw["chart_id"],
        source=raw["dataset_source"],
        chart_type=chart.chart_type,
        domain=chart.domain,
        chart_title=chart.title,
        model_id=raw["model_id"],
        variant=raw["variant"],
        enabled_features=list(raw.get("enabled_features", [])),
        include_image=raw["include_image"],
        created_at=str(raw["created_at"]),
        parse_ok=parse_ok,
        section_schema_ok=section_schema_ok,
        scores=scores,
        sections=sections,
        direct_claims=direct,
        derived_claims=derived,
        speculative_claims=speculative,
        chart=chart,
    )


def load_records(require_complete_coverage: bool = True, verbose: bool = True) -> list[EvalRecord]:
    """
    Loads every (chart, output) pair on disk.

    By default, restricts to charts that have output from all of
    REQUIRED_MODELS — as of this writing that excludes exactly one chart
    (vistext_1, gemini-only). Pass require_complete_coverage=False to get
    everything, e.g. for a coverage audit.
    """
    charts = get_all_charts()
    chart_by_id = {c.chart_id: c for c in charts}

    all_records: list[EvalRecord] = []
    models_by_chart: dict[str, set[str]] = {}

    for chart in charts:
        outputs = load_outputs_for_chart(chart.chart_id)
        if not outputs:
            continue
        models_by_chart[chart.chart_id] = {o.model_id for o in outputs}
        for o in outputs:
            all_records.append(_record_from_output(chart, o.model_dump(mode="json")))

    incomplete = {
        cid: models
        for cid, models in models_by_chart.items()
        if not REQUIRED_MODELS.issubset(models)
    }

    if verbose:
        print(f"[evaluation.common] {len(models_by_chart)} charts with output, "
              f"{len(all_records)} output records total")
        n_bad_schema = sum(1 for r in all_records if r.parse_ok and not r.section_schema_ok)
        if n_bad_schema:
            print(f"[evaluation.common] {n_bad_schema} record(s) had a non-string "
                  f"generated_description field (model schema deviation) — coerced to text")
        if incomplete:
            print(f"[evaluation.common] {len(incomplete)} chart(s) missing full "
                  f"{sorted(REQUIRED_MODELS)} coverage:")
            for cid, models in incomplete.items():
                missing = sorted(REQUIRED_MODELS - models)
                print(f"    {cid}: has {sorted(models)}, missing {missing}")

    if require_complete_coverage:
        all_records = [r for r in all_records if r.chart_id not in incomplete]
        if verbose:
            n_charts = len(models_by_chart) - len(incomplete)
            print(f"[evaluation.common] using {n_charts} charts with complete coverage "
                  f"({len(all_records)} records)")

    return all_records


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[evaluation.common] wrote {len(rows)} rows -> {path.relative_to(_BACKEND_DIR)}")
