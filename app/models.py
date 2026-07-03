from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ItemCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    value: float = 0.0


class ItemUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: float


class ItemPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    value: Optional[float] = None


class Item(BaseModel):
    id: str
    name: str
    value: float
    updated_at: str


class BulkUpsertRequest(BaseModel):
    items: list[ItemCreate] = Field(..., min_length=1, max_length=5000)


class BulkUpsertResult(BaseModel):
    inserted: int
    updated: int
    total: int
    errors: list[str] = []
