from fastapi import APIRouter
from app.services.dataset_service import get_dataset_stats

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/stats")
def dataset_stats():
    return get_dataset_stats()
