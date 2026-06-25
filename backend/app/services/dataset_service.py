"""
Reads chart JSON files from the datasets directory.

Directory layout expected:
  data/
        datasets/
            vistext/
                charts.json          ← list of Chart objects
                images/              ← PNG files referenced by chart.image_path
            olli/
                charts.json
                images/
            vcc/
                charts.json
                images/
            hci_alt_texts/
                charts.json
                images/

Legacy layout is also supported:
    data/
        vistext/
      charts.json          ← list of Chart objects
      images/              ← PNG files referenced by chart.image_path
    olli/
      charts.json
      images/
    vcc/
      charts.json
      images/
    hci_alt_texts/
      charts.json
      images/
"""

from __future__ import annotations
import json
from app.core.config import settings
from app.models.chart import Chart, DatasetSource, ChartType

SOURCES: list[DatasetSource] = ["vistext", "olli", "our_world_data", "vcc", "hci_alt_texts"]

# Consolidation map: old fine-grained types → broad category.
# Also catches any novel type from dataset scripts before Pydantic validates.
_CHART_TYPE_NORMALISE: dict[str, str] = {
    "stacked_bar":  "bar",
    "multi_series": "line",
    "area":         "line",
    "pie":          "other",
    "donut":        "other",
    "arc":          "other",
    "map":          "other",
    "choropleth":   "other",
    "geoshape":     "other",
    "treemap":      "other",
    "sankey":       "other",
    "network":      "other",
}
_VALID_CHART_TYPES = {"bar", "line", "scatter", "heatmap", "box_plot", "other"}


_VL_MARK_OVERRIDES: dict[str, str] = {
    "arc":      "other",   # pie / donut
    "geoshape": "other",   # maps / choropleth
}


def _normalise_chart_type(raw: str) -> str:
    t = raw.lower().replace(" ", "_").replace("-", "_")
    if t in _VALID_CHART_TYPES:
        return t
    return _CHART_TYPE_NORMALISE.get(t, "other")


def _type_from_spec(item: dict) -> str | None:
    """
    Inspect the vega-lite mark to catch charts that were stored with the wrong
    type (e.g. Olli pie/donut/map stored as 'bar' before conversion was fixed).
    Returns the corrected type, or None if no override is needed.
    """
    spec = (item.get("metadata") or {}).get("vega_lite_spec")
    if not spec or not isinstance(spec, dict):
        return None
    mark = spec.get("mark")
    if isinstance(mark, dict):
        mark = mark.get("type")
    if mark:
        return _VL_MARK_OVERRIDES.get(str(mark).lower())
    # Compound specs (layer/concat/hconcat/vconcat with mixed marks) → other
    for key in ("hconcat", "vconcat", "concat"):
        if key in spec:
            return "other"
    return None


def _load_all_charts() -> list[Chart]:
    charts: list[Chart] = []
    for source in SOURCES:
        path = settings.datasets_dir / source / "charts.json"
        if not path.exists():
            continue
        print(f"[dataset_service] loading {path} …", flush=True)
        raw = json.loads(path.read_text())
        skipped = 0
        for item in raw:
            try:
                spec_override = _type_from_spec(item)
                item["chart_type"] = spec_override or _normalise_chart_type(item.get("chart_type", "other"))
                charts.append(Chart.model_validate(item))
            except Exception:
                skipped += 1
        print(f"[dataset_service] {source}: {len(raw) - skipped} charts loaded, {skipped} skipped", flush=True)
    return charts


# Load once at module import time — resets on every uvicorn --reload cycle.
_ALL_CHARTS: list[Chart] = _load_all_charts()


def get_all_charts() -> list[Chart]:
    return _ALL_CHARTS


def get_chart_by_id(chart_id: str) -> Chart | None:
    return next((c for c in get_all_charts() if c.chart_id == chart_id), None)


def filter_charts(
    source: DatasetSource | None = None,
    chart_type: ChartType | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Chart], int]:
    charts = get_all_charts()
    if source:
        charts = [c for c in charts if c.source == source]
    if chart_type:
        charts = [c for c in charts if c.chart_type == chart_type]
    total = len(charts)
    start = (page - 1) * page_size
    return charts[start : start + page_size], total


def get_dataset_stats() -> list[dict]:
    charts = get_all_charts()
    stats = {}
    for c in charts:
        s = stats.setdefault(
            c.source,
            {"source": c.source, "total_charts": 0, "by_chart_type": {}, "by_domain": {}},
        )
        s["total_charts"] += 1
        s["by_chart_type"][c.chart_type] = s["by_chart_type"].get(c.chart_type, 0) + 1
        s["by_domain"][c.domain] = s["by_domain"].get(c.domain, 0) + 1
    return list(stats.values())
