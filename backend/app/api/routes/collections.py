from fastapi import APIRouter, HTTPException
from app.models.collection import Collection, CreateCollectionRequest, UpdateCollectionRequest
from app.models.chart import Chart
from app.services import collection_service
from app.services.dataset_service import get_chart_by_id

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[Collection])
def list_collections():
    return collection_service.list_collections()


@router.post("", response_model=Collection, status_code=201)
def create_collection(req: CreateCollectionRequest):
    return collection_service.create_collection(
        name=req.name,
        chart_ids=req.chart_ids,
        description=req.description,
    )


@router.get("/{collection_id}", response_model=Collection)
def get_collection(collection_id: str):
    col = collection_service.get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.get("/{collection_id}/charts", response_model=list[Chart])
def get_collection_charts(collection_id: str):
    col = collection_service.get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    charts = [get_chart_by_id(cid) for cid in col.chart_ids]
    return [c for c in charts if c is not None]


@router.patch("/{collection_id}", response_model=Collection)
def update_collection(collection_id: str, req: UpdateCollectionRequest):
    col = collection_service.update_collection(
        collection_id=collection_id,
        name=req.name,
        description=req.description,
        chart_ids=req.chart_ids,
    )
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.post("/{collection_id}/charts", response_model=Collection)
def add_charts(collection_id: str, chart_ids: list[str]):
    col = collection_service.add_charts(collection_id, chart_ids)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.delete("/{collection_id}/charts", response_model=Collection)
def remove_charts(collection_id: str, chart_ids: list[str]):
    col = collection_service.remove_charts(collection_id, chart_ids)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: str):
    if not collection_service.delete_collection(collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
