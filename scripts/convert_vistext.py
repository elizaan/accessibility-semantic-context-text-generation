#!/usr/bin/env python3
"""
Convert VisText dataset files into AccessViz charts.json format.

Expected layout inside data/vistext/:
  tabular/data_train.json
  tabular/data_test.json
  tabular/L2L3_captions.json
  scenegraphs/{img_id}.json
  vl_spec/{img_id}.vl.json
  images/{img_id}.png

Output:
  data/vistext/charts.json          — all converted charts (one per unique image)
  data/vistext/charts_subset.json   — curated 150-chart subset (balanced by type/domain)

Run from the repo root:
  python3 scripts/convert_vistext.py
"""

from __future__ import annotations
import json
import re
import random
import collections
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
VISTEXT = ROOT / "data" / "vistext"

TRAIN_JSON       = VISTEXT / "tabular" / "data_train.json"
TEST_JSON        = VISTEXT / "tabular" / "data_test.json"
ALTSEED_TRAIN    = VISTEXT / "tabular" / "data_train_altseed.json"
ALTSEED_TEST     = VISTEXT / "tabular" / "data_test_altseed.json"
L2L3_JSON        = VISTEXT / "tabular" / "L2L3_captions.json"
SCENEGRAPHS    = VISTEXT / "scenegraphs"
VL_SPEC        = VISTEXT / "vl_spec"
IMAGES         = VISTEXT / "images"
OUT_ALL        = VISTEXT / "charts.json"
OUT_SUBSET     = VISTEXT / "charts_subset.json"

# ─── Chart type mapping ───────────────────────────────────────────────────────
# VisText has bar / line / area.  Area is a visual variant of line.

CHART_TYPE_MAP: dict[str, str] = {
    "bar":  "bar",
    "line": "line",
    "area": "line",   # area charts share the same semantic structure as line
}

# ─── Domain keyword inference ─────────────────────────────────────────────────
# Ordered by specificity so more specific domains win ties.

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "public_health": [
        "health", "disease", "vaccine", "vaccination", "covid", "hospital",
        "patient", "mortality", "death", "cancer", "diabetes", "obesity",
        "mental health", "drug", "epidemic", "pandemic", "life expectancy",
        "infant mortality", "suicide", "smoking", "tobacco", "calorie",
        "nutrition", "obesity", "illness", "surgery", "pharmaceutical",
    ],
    "climate": [
        "temperature", "emission", "carbon", "climate", "renewable", "energy",
        "pollution", "greenhouse", "co2", "fossil fuel", "electricity",
        "solar", "wind power", "deforestation", "sea level", "wildfire",
        "drought", "flood", "precipitation", "atmosphere",
    ],
    "finance": [
        "gdp", "revenue", "profit", "stock", "market", "trade", "inflation",
        "price", "economic", "economy", "wage", "salary", "income", "tax",
        "investment", "debt", "budget", "spending", "export", "import",
        "billion", "million dollar", "euro", "cost", "fee", "ticket price",
        "subscription", "revenue", "earnings", "financial", "bank", "fund",
    ],
    "education": [
        "school", "university", "college", "education", "student", "literacy",
        "graduation", "degree", "academic", "enrollment", "teacher", "test score",
        "reading", "mathematics", "tuition",
    ],
    "demographics": [
        "population", "birth rate", "death rate", "migration", "age group",
        "gender", "race", "ethnicity", "urban", "rural", "household",
        "fertility", "life expectancy",
    ],
    "employment": [
        "employment", "unemployment", "job", "labor", "workforce", "worker",
        "occupation", "industry", "hire", "layoff", "productivity", "strike",
    ],
}


def infer_domain(title: str) -> str:
    title_lower = title.lower()
    scores: dict[str, int] = {d: 0 for d in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                scores[domain] += 1
    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain if scores[best_domain] > 0 else "general"


# ─── Datatable parser ─────────────────────────────────────────────────────────
# VisText format: "Chart Title <s> ColHeader1 ColHeader2 val val val ..."
# Column headers come from L1_properties[2] (x-axis) and L1_properties[3] (y-axis).

def parse_datatable(raw: str, x_label: str, y_label: str) -> list[dict] | None:
    if not raw or "<s>" not in raw:
        return None
    try:
        table_text = raw.split("<s>", 1)[1].strip()
        # Strip the known column headers from the start of the string
        for label in [x_label, y_label]:
            if table_text.lower().startswith(label.lower()):
                table_text = table_text[len(label):].strip()

        tokens = table_text.split()
        rows: list[dict] = []
        i = 0
        while i < len(tokens) - 1:
            x_val_str = tokens[i]
            y_val_str = tokens[i + 1]
            # Check if y is numeric (x may be a label or numeric)
            try:
                y_val = float(y_val_str.replace(",", ""))
                try:
                    x_val: float | str = float(x_val_str.replace(",", ""))
                except ValueError:
                    x_val = x_val_str
                rows.append({x_label: x_val, y_label: y_val})
                i += 2
            except ValueError:
                # Non-numeric y — advance one token and try again
                i += 1

        return rows if rows else None
    except Exception:
        return None


# ─── Scenegraph and vl_spec loaders ─────────────────────────────────────────

def load_json_or_none(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─── Main conversion ──────────────────────────────────────────────────────────

def convert() -> list[dict]:
    # 1. Load ALL caption files (train, test, and both altseed variants).
    #    The altseed files contain 811 additional img_ids not present in the
    #    regular train/test files — including them brings us to 8,750 charts.
    #    De-duplicate by img_id, preferring regular train/test entries over
    #    altseed entries (better caption quality).
    print("Loading caption files…")

    # Load regular files first so they take priority in the de-duplication
    priority_entries: list[dict] = []
    for path in [TRAIN_JSON, TEST_JSON]:
        if path.exists():
            priority_entries.extend(json.loads(path.read_text(encoding="utf-8")))

    # Then load altseed files (fallback for img_ids not in regular files)
    altseed_entries: list[dict] = []
    for path in [ALTSEED_TRAIN, ALTSEED_TEST]:
        if path.exists():
            altseed_entries.extend(json.loads(path.read_text(encoding="utf-8")))

    # Build img_id → entry dict: regular entries win, altseed fills the gaps
    by_img: dict[str, dict] = {}
    for entry in priority_entries:
        img_id = str(entry["img_id"])
        if img_id not in by_img:
            by_img[img_id] = entry
    altseed_only = 0
    for entry in altseed_entries:
        img_id = str(entry["img_id"])
        if img_id not in by_img:
            by_img[img_id] = entry
            altseed_only += 1

    print(f"  {len(by_img)} unique img_ids ({altseed_only} added from altseed files)")

    # 2. Load the separate L2L3 captions (one per image, human-written)
    #    Their img_id is stored as an integer in this file
    l2l3_map: dict[str, str] = {}
    try:
        l2l3_data = json.loads(L2L3_JSON.read_text(encoding="utf-8"))
        for item in l2l3_data:
            l2l3_map[str(item["img_id"])] = item["caption_L2L3"]
        print(f"  Loaded {len(l2l3_map)} L2L3 captions")
    except Exception as e:
        print(f"  Warning: could not load L2L3 captions — {e}")

    # 3. Also cover images on disk that have no JSON entry at all but DO have
    #    an L2L3 caption — these 72 charts would otherwise be silently skipped.
    all_image_ids = {f.stem for f in IMAGES.iterdir()
                     if f.suffix == ".png"} if IMAGES.exists() else set()
    image_only_ids = all_image_ids - set(by_img.keys())
    for img_id in image_only_ids:
        # Synthesise a minimal entry so the loop below can process them
        by_img[img_id] = {
            "img_id": img_id,
            "L1_properties": [],
            "caption_L1": None,
            "caption_L2L3": None,
            "scenegraph": None,
            "datatable": None,
        }
    print(f"  +{len(image_only_ids)} image-only charts (no JSON entry, L2L3 from separate file)")

    # 4. Convert each unique image
    charts: list[dict] = []
    missing_images = 0

    for img_id, entry in sorted(by_img.items(), key=lambda x: int(x[0])):
        image_file = IMAGES / f"{img_id}.png"
        if not image_file.exists():
            missing_images += 1
            continue

        l1_props: list[str] = entry.get("L1_properties", [])
        raw_type  = l1_props[0] if len(l1_props) > 0 else "bar"
        title     = l1_props[1] if len(l1_props) > 1 else ""
        x_label   = l1_props[2] if len(l1_props) > 2 else "x"
        y_label   = l1_props[3] if len(l1_props) > 3 else "y"

        chart_type = CHART_TYPE_MAP.get(raw_type, "bar")
        domain     = infer_domain(title)

        # L1 caption — from the tabular entry
        l1_caption = entry.get("caption_L1") or None

        # L2L3 caption — prefer the separate human-written file; fall back to entry
        l2l3_caption = (
            l2l3_map.get(img_id)
            or entry.get("caption_L2L3")
            or None
        )

        # Text-based scenegraph (compact string from tabular file)
        scenegraph_text = entry.get("scenegraph") or None

        # Full JSON scenegraph
        sg_json = load_json_or_none(SCENEGRAPHS / f"{img_id}.json")

        # Vega-Lite spec
        vl_json = load_json_or_none(VL_SPEC / f"{img_id}.vl.json")

        # Data table
        data_table = parse_datatable(entry.get("datatable", ""), x_label, y_label)

        chart: dict = {
            "chart_id": f"vistext_{img_id}",
            "source": "vistext",
            "chart_type": chart_type,
            "domain": domain,
            "image_path": f"vistext/images/{img_id}.png",
            "title": title or None,
            "metadata": {
                "alt_text": None,
                "aria_label": None,
                "aria_describedby": None,
                "olli_tree": None,
                "scene_graph": sg_json,
                "data_table": data_table,
                "vega_lite_spec": vl_json,
                "l1_caption": l1_caption,
                "l2_caption": l2l3_caption,   # combined L2/L3 from VisText
                "l3_caption": None,            # VisText does not separate L2 from L3
                "l4_caption": None,            # our annotation target
                "domain_context": None,
                "stakeholder_context": None,
                "source_url": None,
            },
            "ground_truth_description": {
                "context": "",
                "semantic_meaning": "",
                "real_world_significance": "",
            },
        }
        charts.append(chart)

    print(f"\nConverted {len(charts)} charts ({missing_images} skipped — image not found)")
    return charts


def make_subset(charts: list[dict], target: int = 150) -> list[dict]:
    """
    Balanced subset across chart_type × domain.
    Prioritises charts that have BOTH scene_graph AND l2_caption available
    (richer metadata = more useful for ablation experiments).
    """
    # Sort by richness: prefer charts with scenegraph + l2_caption + vl_spec
    def richness(c: dict) -> int:
        m = c["metadata"]
        score = 0
        if m["scene_graph"]:    score += 3
        if m["l2_caption"]:     score += 2
        if m["vega_lite_spec"]: score += 2
        if m["data_table"]:     score += 1
        return score

    charts_sorted = sorted(charts, key=richness, reverse=True)

    # Group by (chart_type, domain)
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for c in charts_sorted:
        groups[(c["chart_type"], c["domain"])].append(c)

    subset: list[dict] = []
    remaining = target
    keys = list(groups.keys())
    random.seed(42)
    random.shuffle(keys)

    # First pass: take up to ceil(target / n_groups) from each group
    per_group = max(1, target // len(keys))
    for key in keys:
        take = min(per_group, len(groups[key]), remaining)
        subset.extend(groups[key][:take])
        remaining -= take
        if remaining <= 0:
            break

    # Second pass: fill remaining from the richest charts not yet included
    if remaining > 0:
        ids_in_subset = {c["chart_id"] for c in subset}
        for c in charts_sorted:
            if remaining <= 0:
                break
            if c["chart_id"] not in ids_in_subset:
                subset.append(c)
                remaining -= 1

    return subset


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)

    charts = convert()

    # ── Summary stats ────────────────────────────────────────────────────────
    type_counts  = collections.Counter(c["chart_type"] for c in charts)
    domain_counts = collections.Counter(c["domain"] for c in charts)
    meta_counts  = {
        "has_scene_graph":    sum(1 for c in charts if c["metadata"]["scene_graph"]),
        "has_vl_spec":        sum(1 for c in charts if c["metadata"]["vega_lite_spec"]),
        "has_data_table":     sum(1 for c in charts if c["metadata"]["data_table"]),
        "has_l1_caption":     sum(1 for c in charts if c["metadata"]["l1_caption"]),
        "has_l2_caption":     sum(1 for c in charts if c["metadata"]["l2_caption"]),
    }

    print("\n── Chart types ──")
    for t, n in type_counts.most_common():
        print(f"  {t:15s} {n}")

    print("\n── Domains (inferred) ──")
    for d, n in domain_counts.most_common():
        print(f"  {d:20s} {n}")

    print("\n── Metadata coverage ──")
    for k, n in meta_counts.items():
        print(f"  {k:25s} {n} / {len(charts)}")

    # ── Write all charts ─────────────────────────────────────────────────────
    OUT_ALL.write_text(json.dumps(charts, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(charts)} charts → {OUT_ALL}")

    # ── Write balanced subset ────────────────────────────────────────────────
    subset = make_subset(charts, target=150)
    OUT_SUBSET.write_text(json.dumps(subset, indent=2, ensure_ascii=False))
    print(f"Wrote {len(subset)} charts → {OUT_SUBSET}")

    # ── Show subset distribution ─────────────────────────────────────────────
    print("\n── Subset: chart types ──")
    for t, n in collections.Counter(c["chart_type"] for c in subset).most_common():
        print(f"  {t:15s} {n}")
    print("\n── Subset: domains ──")
    for d, n in collections.Counter(c["domain"] for c in subset).most_common():
        print(f"  {d:20s} {n}")
