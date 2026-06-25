from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class Collection(BaseModel):
    collection_id: str
    name: str
    description: str | None = None
    chart_ids: list[str]
    created_at: datetime
    updated_at: datetime


class CreateCollectionRequest(BaseModel):
    name: str
    description: str | None = None
    chart_ids: list[str] = []


class UpdateCollectionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    chart_ids: list[str] | None = None
