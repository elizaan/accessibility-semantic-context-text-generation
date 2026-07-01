from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from app.core.config import settings
from app.models.collection import Collection

_FILE = settings.data_dir / "collections" / "collections.json"


def _load() -> list[Collection]:
    if not _FILE.exists():
        return []
    return [Collection.model_validate(c) for c in json.loads(_FILE.read_text())]


def _save(collections: list[Collection]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps([c.model_dump(mode="json") for c in collections], indent=2))


def list_collections() -> list[Collection]:
    return _load()


def get_collection(collection_id: str) -> Collection | None:
    return next((c for c in _load() if c.collection_id == collection_id), None)


def create_collection(name: str, chart_ids: list[str], description: str | None = None) -> Collection:
    now = datetime.now(timezone.utc)
    col = Collection(
        collection_id=str(uuid.uuid4()),
        name=name,
        description=description,
        chart_ids=chart_ids,
        created_at=now,
        updated_at=now,
    )
    cols = _load()
    cols.append(col)
    _save(cols)
    return col


def update_collection(
    collection_id: str,
    name: str | None = None,
    description: str | None = None,
    chart_ids: list[str] | None = None,
) -> Collection | None:
    cols = _load()
    for i, c in enumerate(cols):
        if c.collection_id == collection_id:
            patch = {k: v for k, v in {"name": name, "description": description, "chart_ids": chart_ids}.items() if v is not None}
            patch["updated_at"] = datetime.now(timezone.utc)
            updated = c.model_copy(update=patch)
            cols[i] = updated
            _save(cols)
            return updated
    return None


def add_charts(collection_id: str, chart_ids: list[str]) -> Collection | None:
    cols = _load()
    for i, c in enumerate(cols):
        if c.collection_id == collection_id:
            existing = set(c.chart_ids)
            merged = c.chart_ids + [cid for cid in chart_ids if cid not in existing]
            updated = c.model_copy(update={"chart_ids": merged, "updated_at": datetime.now(timezone.utc)})
            cols[i] = updated
            _save(cols)
            return updated
    return None


def remove_charts(collection_id: str, chart_ids: list[str]) -> Collection | None:
    remove_set = set(chart_ids)
    cols = _load()
    for i, c in enumerate(cols):
        if c.collection_id == collection_id:
            updated = c.model_copy(update={
                "chart_ids": [cid for cid in c.chart_ids if cid not in remove_set],
                "updated_at": datetime.now(timezone.utc),
            })
            cols[i] = updated
            _save(cols)
            return updated
    return None


def delete_collection(collection_id: str) -> bool:
    cols = _load()
    new_cols = [c for c in cols if c.collection_id != collection_id]
    if len(new_cols) == len(cols):
        return False
    _save(new_cols)
    return True


def reorder_collections(ordered_ids: list[str]) -> list[Collection]:
    cols = _load()
    by_id = {c.collection_id: c for c in cols}
    reordered = [by_id[cid] for cid in ordered_ids if cid in by_id]
    remaining = [c for c in cols if c.collection_id not in set(ordered_ids)]
    new_cols = reordered + remaining
    _save(new_cols)
    return new_cols
