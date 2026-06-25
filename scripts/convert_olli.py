#!/usr/bin/env python3
"""
Convert Olli gallery specs into AccessViz charts.json format.

Prerequisites:
  pip install vl-convert-python

Workflow:
  1. Run fetch script first:       node scripts/fetch_olli_specs.mjs
  2. Then run this converter:      python3 scripts/convert_olli.py

Input:   data/olli/raw_specs.json   (produced by fetch_olli_specs.mjs)
Output:  data/olli/charts.json
         data/olli/images/<id>.png  (rendered PNGs)

Run from the repo root.
"""

from __future__ import annotations
import json
import collections
from pathlib import Path

try:
    import vl_convert as vlc
except ImportError:
    raise SystemExit(
        "vl-convert-python is not installed.\n"
        "Run:  pip install vl-convert-python\n"
        "or:   backend/.venv/bin/pip install vl-convert-python"
    )

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).parent.parent
OLLI_DIR  = ROOT / "data" / "olli"
RAW_SPECS = OLLI_DIR / "raw_specs.json"
IMAGES    = OLLI_DIR / "images"
OUT       = OLLI_DIR / "charts.json"

IMAGES.mkdir(parents=True, exist_ok=True)

# ─── Domain inference (same keyword logic as convert_vistext.py) ──────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "public_health": [
        "health", "disease", "vaccine", "covid", "hospital", "mortality",
        "death", "cancer", "obesity", "epidemic", "pandemic", "life expectancy",
    ],
    "climate": [
        "temperature", "emission", "carbon", "climate", "renewable", "energy",
        "pollution", "greenhouse", "co2", "solar", "wind",
    ],
    "finance": [
        "gdp", "revenue", "profit", "stock", "market", "trade", "inflation",
        "price", "economic", "economy", "wage", "income", "cost",
    ],
    "education": [
        "school", "university", "education", "student", "literacy", "graduation",
        "enrollment", "teacher", "reading", "mathematics",
    ],
    "demographics": [
        "population", "birth", "migration", "age", "gender", "race",
        "ethnicity", "urban", "rural", "household", "fertility",
    ],
    "employment": [
        "employment", "unemployment", "job", "labor", "workforce", "worker",
        "occupation", "productivity",
    ],
}


def infer_domain(title: str, description: str | None = None) -> str:
    text = (title + " " + (description or "")).lower()
    scores: dict[str, int] = {d: 0 for d in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[domain] += 1
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] > 0 else "general"


# ─── PNG rendering ────────────────────────────────────────────────────────────

def render_png(spec: dict, chart_id: str) -> str | None:
    """Render Vega-Lite spec to PNG; return relative image_path or None."""
    out_path = IMAGES / f"{chart_id}.png"
    try:
        png_bytes = vlc.vegalite_to_png(spec, scale=2.0)
        out_path.write_bytes(png_bytes)
        return f"olli/images/{chart_id}.png"
    except Exception as e:
        print(f"  ! PNG render failed for {chart_id}: {e}")
        return None


# ─── Data table extraction from inline Vega-Lite data ─────────────────────────

def extract_data_table(spec: dict) -> list[dict] | None:
    """Extract inline data values from the Vega-Lite spec."""
    # Walk through nested specs to find the first inline data
    def _find(s: dict) -> list | None:
        if "data" in s and isinstance(s["data"], dict):
            vals = s["data"].get("values")
            if isinstance(vals, list) and vals:
                return vals
        for key in ("layer", "concat", "hconcat", "vconcat"):
            if key in s and isinstance(s[key], list):
                for sub in s[key]:
                    r = _find(sub)
                    if r is not None:
                        return r
        if "spec" in s:
            return _find(s["spec"])
        return None

    rows = _find(spec)
    if not rows:
        return None
    # Keep only simple primitive values to avoid cluttering the model prompt
    clean = [{k: v for k, v in row.items() if not isinstance(v, (dict, list))}
             for row in rows]
    return clean if clean else None


# ─── Chart type inference from Vega-Lite spec ────────────────────────────────

def _primary_mark(spec: dict) -> str:
    """Recursively find the primary Vega-Lite mark type."""
    if not spec:
        return ""
    m = spec.get("mark")
    if m:
        return (m.get("type") if isinstance(m, dict) else m) or ""
    # Compound specs: prefer 'layer' (first sub-spec), then concat variants
    for key in ("layer", "hconcat", "vconcat", "concat"):
        subs = spec.get(key)
        if subs and isinstance(subs, list):
            # A compound spec is "other" unless all sub-marks are the same simple type
            marks = {_primary_mark(s) for s in subs}
            marks.discard("")
            return marks.pop() if len(marks) == 1 else "_compound_"
    if "spec" in spec:
        return _primary_mark(spec["spec"])
    return ""


# Vega-Lite mark → AccessViz chart type
_VL_MARK_TO_TYPE: dict[str, str] = {
    "bar":      "bar",
    "line":     "line",
    "area":     "line",   # area is a line variant
    "point":    "scatter",
    "circle":   "scatter",
    "square":   "scatter",
    "tick":     "scatter",
    "rect":     "heatmap",
    "boxplot":  "box_plot",
    "arc":      "other",      # pie / donut
    "geoshape": "other",      # maps / choropleth
    "_compound_": "other",    # concat / layer with mixed marks
}


def infer_chart_type(spec: dict, raw_type: str | None = None) -> str:
    """
    Derive the AccessViz chart type from the Vega-Lite spec mark.
    Falls back to raw_type from the Olli entry when the mark is unrecognised.
    """
    mark = _primary_mark(spec).lower()
    if mark in _VL_MARK_TO_TYPE:
        return _VL_MARK_TO_TYPE[mark]
    # Use the Olli-provided type if it maps to one of our categories
    _LEGACY = {"bar", "line", "scatter", "heatmap", "box_plot"}
    if raw_type and raw_type.lower() in _LEGACY:
        return raw_type.lower()
    return "other"


# ─── Main ─────────────────────────────────────────────────────────────────────

def convert() -> list[dict]:
    if not RAW_SPECS.exists():
        raise SystemExit(
            f"{RAW_SPECS} not found.\n"
            "Run the fetch script first:  node scripts/fetch_olli_specs.mjs"
        )

    raw = json.loads(RAW_SPECS.read_text(encoding="utf-8"))
    print(f"Converting {len(raw)} Olli specs…\n")

    charts: list[dict] = []
    ok, failed = 0, 0

    for entry in raw:
        chart_id   = f"olli_{entry['id']}"
        spec       = entry.get("vl_spec") or {}
        title      = entry.get("title") or entry["id"].replace("-", " ").title()
        description = entry.get("description")
        chart_type  = infer_chart_type(spec, entry.get("chart_type"))
        domain      = infer_domain(title, description)

        print(f"  {entry['id']:35s}  type={chart_type:10s}  domain={domain}")

        image_path = render_png(spec, entry["id"]) if spec else None
        if image_path:
            ok += 1
        else:
            failed += 1

        data_table = extract_data_table(spec) if spec else None

        chart: dict = {
            "chart_id": chart_id,
            "source": "olli",
            "chart_type": chart_type,
            "domain": domain,
            "image_path": image_path,
            "title": title,
            "metadata": {
                "alt_text": None,
                "aria_label": None,
                "aria_describedby": None,
                "olli_tree": None,       # generated at runtime by Olli JS library
                "scene_graph": None,
                "data_table": data_table,
                "vega_lite_spec": spec or None,
                "l1_caption": None,
                "l2_caption": None,
                "l3_caption": None,
                "l4_caption": None,
                "domain_context": description,
                "stakeholder_context": None,
                "source_url": f"https://umwelt-data.github.io/olli/gallery/#{entry['id']}",
            },
            "ground_truth_description": {
                "context": "",
                "semantic_meaning": "",
                "real_world_significance": "",
            },
        }
        charts.append(chart)

    return charts, ok, failed


if __name__ == "__main__":
    charts, ok, failed = convert()

    type_counts   = collections.Counter(c["chart_type"] for c in charts)
    domain_counts = collections.Counter(c["domain"] for c in charts)
    has_image     = sum(1 for c in charts if c["image_path"])
    has_data      = sum(1 for c in charts if c["metadata"]["data_table"])
    has_spec      = sum(1 for c in charts if c["metadata"]["vega_lite_spec"])

    print("\n── Chart types ──")
    for t, n in type_counts.most_common():
        print(f"  {t:20s} {n}")

    print("\n── Domains (inferred) ──")
    for d, n in domain_counts.most_common():
        print(f"  {d:20s} {n}")

    print("\n── Metadata coverage ──")
    total = len(charts)
    print(f"  image           {has_image} / {total}")
    print(f"  vega_lite_spec  {has_spec} / {total}")
    print(f"  data_table      {has_data} / {total}")
    print(f"  olli_tree       0 / {total}  (JS-generated at runtime — add manually)")

    OUT.write_text(json.dumps(charts, indent=2, ensure_ascii=False))
    print(f"\nWrote {total} charts → {OUT}")
    print(f"PNG renders: {ok} ok, {failed} failed")
    print("\nNote: olli_tree values are generated at runtime by the Olli JS library.")
    print("To add them: open each chart in the Olli gallery, copy the ARIA tree")
    print("text from the Olli panel, and paste it into the olli_tree field.")
