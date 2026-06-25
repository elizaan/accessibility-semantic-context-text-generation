from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models.chart import DatasetSource, ChartType
from app.services.dataset_service import get_chart_by_id, filter_charts

router = APIRouter(prefix="/charts", tags=["charts"])

# Heavy metadata fields — omitted in summary mode to keep list responses small
_HEAVY_FIELDS = {"scene_graph", "vega_lite_spec", "data_table"}


def _summarize(chart) -> dict:
    """Strip heavy JSON fields for grid/list views. Keeps all string fields."""
    d = chart.model_dump()
    for field in _HEAVY_FIELDS:
        if d["metadata"].get(field) is not None:
            d["metadata"][field] = True   # replaced with boolean so UI knows it exists
    return d


@router.get("")
def list_charts(
    source: Optional[DatasetSource] = Query(None),
    chart_type: Optional[ChartType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=20000),
    summary: bool = Query(True),   # True = strip heavy fields (fast), False = full records
):
    charts, total = filter_charts(source=source, chart_type=chart_type, page=page, page_size=page_size)
    payload = [_summarize(c) for c in charts] if summary else [c.model_dump() for c in charts]
    return {"charts": payload, "total": total, "page": page, "page_size": page_size}


@router.get("/{chart_id}")
def get_chart(chart_id: str):
    chart = get_chart_by_id(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return chart
