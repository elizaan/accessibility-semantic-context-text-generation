"""
Extracts every individual claim (one row per [DIRECT]/[DERIVED]/[SPECULATIVE]
tagged span) from the generated outputs of a fixed set of charts, for
manual human tagging — e.g. in Google Sheets.

The model's own DIRECT/DERIVED/SPECULATIVE tag is stripped out of the
claim text entirely and not written anywhere in the output, so the human
tagger judges each claim cold, without being anchored by the model's own
self-assessment. A blank "tagged_by_human" column is provided instead.

Chart identity is shown as the DEPLOYED site's "source #N" serial number
(matching what's shown in the Datasets grid / Compare picker), not the
raw internal chart_id — so you can cross-reference directly against what
you see on the deployed site while tagging.

Selected charts: the 10 explicitly requested (vistext #11/17/28, olli
#7/10, hci #20, owid #4/17/1/20) plus 2 more picked as interesting either
because a claim on them was independently verified as a genuine
hallucination (vistext #17, olli #7 — both were already in the requested
list) or because they illustrate a different, non-obvious failure mode
worth a second pair of eyes: owid #15 (lighting-sources-uk) and olli #2
(area-chart), both cases where the automated value_fidelity checker
originally flagged the claim as "fabricated" but manual verification
against the real chart image/data showed the model was actually correct
— worth an independent human read since the automated check disagreed
with itself on inspection.

Usage (from repo root): python3 scripts/export_claims_for_tagging.py
Writes scripts/out/claims_for_tagging.csv (or pass a path as argv[1]).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "data" / "outputs" / "runs"
STATIC_DATA_DIR = REPO_ROOT / "frontend" / "public" / "static-data" / "charts-by-source"

# (source key for the deployed static-data file, display label, chart_id)
CHARTS = [
    ("vistext", "vistext", "vistext_428"),          # vistext #11
    ("vistext", "vistext", "vistext_710"),           # vistext #17 — confirmed hallucination (NYT net income sign/magnitude)
    ("vistext", "vistext", "vistext_1280"),          # vistext #28
    ("olli", "olli", "olli_scatterplot"),            # olli #7 — confirmed hallucination (penguin species miscounts)
    ("olli", "olli", "olli_strip-plot"),             # olli #10
    ("hci_alt_texts", "hci", "hci_79b8dcb17db71e75b3401e6743e194cf0943b960_Image_003"),  # hci #20
    ("our_world_data", "owid", "owid_historical_share_of_population_living_on_less_than_5_per_day_roser_hasell"),  # owid #4
    ("our_world_data", "owid", "owid_so_emissions_by_world_region_in_million_tonnes"),  # owid #17
    ("our_world_data", "owid", "owid_life_expectancy"),  # owid #1
    ("our_world_data", "owid", "owid_learning_adjusted_years_of_schooling_vs_electoral_democracy_index"),  # owid #20
    ("our_world_data", "owid", "owid_lighting_sources_uk"),  # owid #15 — added: checker flagged "fabricated", real chart image shows the claim was actually correct
    ("olli", "olli", "olli_area-chart"),             # olli #2 — added: same pattern, precise % claim checker flagged wrongly
]

SECTION_KEYS = ("contextual_insights", "domain_specific_explanations", "real_world_significance", "other")

INLINE_FLAG_PATTERN = re.compile(r"\[(DIRECT|DERIVED|SPECULATIVE)(?::[^\]]*)?\]")


_ALNUM_PATTERN = re.compile(r"[A-Za-z0-9]")


def _is_meaningful(claim_text: str) -> bool:
    """Drops leftover punctuation-only fragments (e.g. a trailing "."
    after the last tag in a section) — not real claims, just noise for
    the tagger to skip past."""
    return len(_ALNUM_PATTERN.findall(claim_text)) >= 3


def split_into_claims(text: str) -> list[str]:
    """Splits text on inline flag tags, returns just the claim text for
    each span with the tag itself removed — the human tagger never sees
    which label the model gave its own claim."""
    claims = []
    last_end = 0
    for match in INLINE_FLAG_PATTERN.finditer(text):
        claim_text = text[last_end:match.start()].strip()
        if _is_meaningful(claim_text):
            claims.append(claim_text)
        last_end = match.end()
    tail = text[last_end:].strip()
    if _is_meaningful(tail):
        claims.append(tail)
    return claims


def deployed_serial(source_key: str, chart_id: str) -> int | None:
    path = STATIC_DATA_DIR / f"{source_key}.json"
    data = json.loads(path.read_text())
    for i, c in enumerate(data["charts"]):
        if c["chart_id"] == chart_id:
            return i + 1
    return None


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "scripts" / "out" / "claims_for_tagging.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    row_id = 0
    for source_key, label, chart_id in CHARTS:
        serial = deployed_serial(source_key, chart_id)
        chart_display = f"{label} #{serial}" if serial else chart_id
        chart_dir = RUNS_DIR / chart_id
        if not chart_dir.exists():
            print(f"WARNING: no outputs found for {chart_id} — skipping")
            continue

        outputs = []
        for f in chart_dir.glob("*.json"):
            outputs.append(json.loads(f.read_text()))
        # Stable, readable ordering: model name, then variant.
        outputs.sort(key=lambda o: (o["model_id"], o["variant"]))

        for output in outputs:
            parsed = output.get("parsed_output") or {}
            desc = parsed.get("generated_description") or {}
            for section in SECTION_KEYS:
                text = desc.get(section, "")
                if not isinstance(text, str) or not text:
                    continue
                for claim_text in split_into_claims(text):
                    row_id += 1
                    rows.append({
                        "row_id": row_id,
                        "chart": chart_display,
                        "model": output["model_id"],
                        "variant": output["variant"],
                        "section": section,
                        "claim_text": claim_text,
                        "tagged_by_human": "",
                    })

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["row_id", "chart", "model", "variant", "section", "claim_text", "tagged_by_human"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} claim rows across {len(CHARTS)} charts -> {out_path}")


if __name__ == "__main__":
    main()
