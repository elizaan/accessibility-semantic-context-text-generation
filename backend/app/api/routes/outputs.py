from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.llm_service import load_all_outputs, load_outputs_for_chart, delete_output

router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.get("")
def list_outputs(
    chart_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    outputs, total = load_all_outputs(model_id=model_id, chart_id=chart_id, page=page, page_size=page_size)
    return {"outputs": outputs, "total": total}


@router.delete("/{output_id}")
def remove_output(output_id: str):
    if not delete_output(output_id):
        raise HTTPException(status_code=404, detail="Output not found")
    return {"deleted": output_id}
