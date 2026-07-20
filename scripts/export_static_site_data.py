"""
Builds a curated, static snapshot of the benchmark for GitHub Pages.

Selects only chart_ids that (a) have a full run of generated outputs under
data/outputs/runs/ AND (b) are referenced by at least one collection in
data/collections/collections.json. That intersection is the "complete and
curated" set (currently 102 charts) — it naturally excludes incomplete runs
(e.g. a chart that only ran through one of three models) without needing a
hardcoded exclusion list.

Output mirrors the shape of the live FastAPI responses 1:1 so the frontend's
static-mode adapter (frontend/lib/static-adapter.ts) can be a near-passthrough:

  frontend/public/static-data/
    dataset-stats.json                    DatasetStats[]
    charts-all.json                       {charts: Chart[], total}   (summarized)
    charts-by-source/<source>.json        {charts: Chart[], total}   (summarized)
    charts/<chart_id>.json                Chart                     (full)
    outputs-by-chart/<chart_id>.json      GenerationOutput[]
    outputs-all.json                      {outputs: GenerationOutput[], total}
    collections.json                      Collection[]              (filtered)
    collections/<collection_id>.json      Collection
    collection-charts/<collection_id>.json Chart[]                  (full)
  frontend/public/static-images/<source>/images/<file>   (only images actually used)

Run manually and commit the output whenever the curated chart set changes —
data/datasets/ is gitignored and unavailable in CI, so this cannot run there.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DATASETS_DIR = DATA_DIR / "datasets"
RUNS_DIR = DATA_DIR / "outputs" / "runs"
COLLECTIONS_PATH = DATA_DIR / "collections" / "collections.json"

OUT_DATA_DIR = REPO_ROOT / "frontend" / "public" / "static-data"
OUT_IMAGES_DIR = REPO_ROOT / "frontend" / "public" / "static-images"

SOURCES = ["vistext", "olli", "our_world_data", "vcc", "hci_alt_texts"]
HEAVY_FIELDS = {"scene_graph", "vega_lite_spec", "data_table"}

# Mirrors backend/app/services/dataset_service.py exactly, so chart-type
# groupings in the static build match what the live app would show.
_CHART_TYPE_NORMALISE = {
    "stacked_bar": "bar",
    "multi_series": "line",
    "area": "line",
    "pie": "other",
    "donut": "other",
    "arc": "other",
    "map": "other",
    "choropleth": "other",
    "geoshape": "other",
    "treemap": "other",
    "sankey": "other",
    "network": "other",
}
_VALID_CHART_TYPES = {"bar", "line", "scatter", "heatmap", "box_plot", "other"}
_VL_MARK_OVERRIDES = {"arc": "other", "geoshape": "other"}


def normalise_chart_type(raw: str) -> str:
    t = raw.lower().replace(" ", "_").replace("-", "_")
    if t in _VALID_CHART_TYPES:
        return t
    return _CHART_TYPE_NORMALISE.get(t, "other")


def type_from_spec(item: dict) -> str | None:
    spec = (item.get("metadata") or {}).get("vega_lite_spec")
    if not spec or not isinstance(spec, dict):
        return None
    mark = spec.get("mark")
    if isinstance(mark, dict):
        mark = mark.get("type")
    if mark:
        return _VL_MARK_OVERRIDES.get(str(mark).lower())
    for key in ("hconcat", "vconcat", "concat"):
        if key in spec:
            return "other"
    return None


def summarize(chart: dict) -> dict:
    d = json.loads(json.dumps(chart))
    for field in HEAVY_FIELDS:
        if d.get("metadata", {}).get(field) is not None:
            d["metadata"][field] = True
    return d


def main() -> None:
    produced_ids = {p.name for p in RUNS_DIR.iterdir() if p.is_dir()}

    raw_collections = json.loads(COLLECTIONS_PATH.read_text())
    referenced_ids: set[str] = set()
    for col in raw_collections:
        referenced_ids.update(col["chart_ids"])

    valid_ids = produced_ids & referenced_ids
    print(f"produced: {len(produced_ids)}  referenced by a collection: {len(referenced_ids)}  curated (intersection): {len(valid_ids)}")

    # ─── Charts ─────────────────────────────────────────────────────────────
    charts_by_id: dict[str, dict] = {}
    charts_by_source: dict[str, list[dict]] = {s: [] for s in SOURCES}

    for source in SOURCES:
        path = DATASETS_DIR / source / "charts.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        for item in raw:
            if item["chart_id"] not in valid_ids:
                continue
            spec_override = type_from_spec(item)
            item["chart_type"] = spec_override or normalise_chart_type(item.get("chart_type", "other"))
            charts_by_id[item["chart_id"]] = item
            charts_by_source[source].append(item)

    missing = valid_ids - set(charts_by_id)
    if missing:
        print(f"WARNING: {len(missing)} curated chart_ids not found in any charts.json: {sorted(missing)}")

    # ─── Outputs ────────────────────────────────────────────────────────────
    outputs_by_chart: dict[str, list[dict]] = {}
    all_outputs: list[dict] = []
    for chart_id in sorted(valid_ids):
        chart_dir = RUNS_DIR / chart_id
        if not chart_dir.exists():
            continue
        outs = [json.loads(p.read_text()) for p in sorted(chart_dir.glob("*.json"))]
        outputs_by_chart[chart_id] = outs
        all_outputs.extend(outs)

    # ─── Collections ────────────────────────────────────────────────────────
    filtered_collections = []
    for col in raw_collections:
        col = dict(col)
        col["chart_ids"] = [cid for cid in col["chart_ids"] if cid in valid_ids]
        if col["chart_ids"]:
            filtered_collections.append(col)
    dropped = len(raw_collections) - len(filtered_collections)
    print(f"collections: {len(raw_collections)} total, {dropped} dropped (became empty), {len(filtered_collections)} kept")

    # ─── Dataset stats (recomputed over curated set only) ──────────────────
    stats: dict[str, dict] = {}
    for chart in charts_by_id.values():
        s = stats.setdefault(
            chart["source"],
            {"source": chart["source"], "total_charts": 0, "by_chart_type": {}, "by_domain": {}},
        )
        s["total_charts"] += 1
        s["by_chart_type"][chart["chart_type"]] = s["by_chart_type"].get(chart["chart_type"], 0) + 1
        s["by_domain"][chart["domain"]] = s["by_domain"].get(chart["domain"], 0) + 1

    # ─── Write it all out ───────────────────────────────────────────────────
    if OUT_DATA_DIR.exists():
        shutil.rmtree(OUT_DATA_DIR)
    if OUT_IMAGES_DIR.exists():
        shutil.rmtree(OUT_IMAGES_DIR)
    OUT_DATA_DIR.mkdir(parents=True)
    OUT_IMAGES_DIR.mkdir(parents=True)

    def write_json(rel_path: str, payload) -> None:
        out_path = OUT_DATA_DIR / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=None, separators=(",", ":")))

    write_json("dataset-stats.json", list(stats.values()))

    all_charts_summarized = [summarize(c) for c in charts_by_id.values()]
    write_json("charts-all.json", {"charts": all_charts_summarized, "total": len(all_charts_summarized)})

    for source, charts in charts_by_source.items():
        if not charts:
            continue
        summarized = [summarize(c) for c in charts]
        write_json(f"charts-by-source/{source}.json", {"charts": summarized, "total": len(summarized)})

    for chart_id, chart in charts_by_id.items():
        write_json(f"charts/{chart_id}.json", chart)

    for chart_id, outs in outputs_by_chart.items():
        write_json(f"outputs-by-chart/{chart_id}.json", outs)

    write_json("outputs-all.json", {"outputs": all_outputs, "total": len(all_outputs)})

    write_json("collections.json", filtered_collections)
    for col in filtered_collections:
        write_json(f"collections/{col['collection_id']}.json", col)
        col_charts = [charts_by_id[cid] for cid in col["chart_ids"] if cid in charts_by_id]
        write_json(f"collection-charts/{col['collection_id']}.json", col_charts)

    # ─── Images ─────────────────────────────────────────────────────────────
    copied = 0
    for chart in charts_by_id.values():
        src = DATASETS_DIR / chart["image_path"]
        if not src.exists():
            print(f"WARNING: image missing for {chart['chart_id']}: {src}")
            continue
        dst = OUT_IMAGES_DIR / chart["image_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    print(f"charts: {len(charts_by_id)}  outputs: {len(all_outputs)}  collections: {len(filtered_collections)}  images copied: {copied}")
    print("per-source chart counts:", {s: len(c) for s, c in charts_by_source.items() if c})


if __name__ == "__main__":
    main()
