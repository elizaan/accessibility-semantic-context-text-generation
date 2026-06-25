from fastapi import APIRouter, HTTPException
from app.models.output import GenerationRequest
from app.services.dataset_service import get_chart_by_id
from app.services.llm_service import generate

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("")
def generate_description(req: GenerationRequest):
    chart = get_chart_by_id(req.chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail=f"Chart '{req.chart_id}' not found")
    output = generate(chart, req)
    return output
