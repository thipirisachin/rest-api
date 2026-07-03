from fastapi import APIRouter, Depends, HTTPException, status
from app.db import db
from app.models import Item, ItemCreate, ItemUpdate, ItemPatch, BulkUpsertRequest, BulkUpsertResult, utcnow
from app.auth import require_token

router = APIRouter(prefix="/items", tags=["items"])


def _row_to_item(row) -> Item:
    return Item(id=row["id"], name=row["name"], value=row["value"], updated_at=row["updated_at"])


@router.get("", response_model=list[Item])
def list_items():
    with db() as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    return [_row_to_item(r) for r in rows]


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return _row_to_item(row)


@router.post("", response_model=Item, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_token)])
def create_item(body: ItemCreate):
    now = utcnow()
    with db() as conn:
        existing = conn.execute("SELECT id FROM items WHERE id = ?", (body.id,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Item '{body.id}' already exists")
        conn.execute(
            "INSERT INTO items (id, name, value, updated_at) VALUES (?, ?, ?, ?)",
            (body.id, body.name, body.value, now),
        )
    return Item(id=body.id, name=body.name, value=body.value, updated_at=now)


@router.put("/{item_id}", response_model=Item, dependencies=[Depends(require_token)])
def replace_item(item_id: str, body: ItemUpdate):
    now = utcnow()
    with db() as conn:
        result = conn.execute(
            "UPDATE items SET name = ?, value = ?, updated_at = ? WHERE id = ?",
            (body.name, body.value, now, item_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return Item(id=item_id, name=body.name, value=body.value, updated_at=now)


@router.patch("/{item_id}", response_model=Item, dependencies=[Depends(require_token)])
def patch_item(item_id: str, body: ItemPatch):
    with db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
        name = body.name if body.name is not None else row["name"]
        value = body.value if body.value is not None else row["value"]
        now = utcnow()
        conn.execute(
            "UPDATE items SET name = ?, value = ?, updated_at = ? WHERE id = ?",
            (name, value, now, item_id),
        )
    return Item(id=item_id, name=name, value=value, updated_at=now)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_token)])
def delete_item(item_id: str):
    with db() as conn:
        result = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")


@router.post("/bulk", response_model=BulkUpsertResult, dependencies=[Depends(require_token)])
def bulk_upsert(body: BulkUpsertRequest):
    now = utcnow()
    inserted = 0
    updated = 0
    errors: list[str] = []

    with db() as conn:
        existing_ids = {
            row[0] for row in conn.execute("SELECT id FROM items").fetchall()
        }
        for item in body.items:
            try:
                if item.id in existing_ids:
                    conn.execute(
                        "UPDATE items SET name = ?, value = ?, updated_at = ? WHERE id = ?",
                        (item.name, item.value, now, item.id),
                    )
                    updated += 1
                else:
                    conn.execute(
                        "INSERT INTO items (id, name, value, updated_at) VALUES (?, ?, ?, ?)",
                        (item.id, item.name, item.value, now),
                    )
                    existing_ids.add(item.id)
                    inserted += 1
            except Exception as e:
                errors.append(f"{item.id}: {e}")

    return BulkUpsertResult(inserted=inserted, updated=updated, total=inserted + updated, errors=errors)
