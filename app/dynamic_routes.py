from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, create_model
from fastapi import APIRouter, Depends, HTTPException, status
from app.db import db
from app.auth import require_token
from app.schema import EntityDef

_PY_TYPES = {"text": str, "integer": int, "real": float}

_AUTH_ERRORS = {
    401: {"description": "Invalid or missing bearer token"},
    500: {"description": "API_TOKEN not configured"},
}
_404 = {404: {"description": "Record not found"}}
_409 = {409: {"description": "Record already exists"}}


class BulkResult(BaseModel):
    inserted: int
    updated: int
    total: int
    errors: list[str]


def _model_name(entity_name: str, suffix: str) -> str:
    return entity_name.title().replace("_", "") + suffix


def _make_record_model(entity: EntityDef):
    """Response model — all fields including id and updated_at."""
    fields: dict[str, Any] = {"id": (str, ...)}
    for f in entity.user_fields:
        py = _PY_TYPES.get(f.type, str)
        fields[f.name] = (py, ...) if f.required else (Optional[py], None)
    fields["updated_at"] = (str, ...)
    return create_model(_model_name(entity.name, "Record"), **fields)


def _make_create_model(entity: EntityDef):
    """POST body — id required, plus entity fields per their required flags."""
    fields: dict[str, Any] = {"id": (str, ...)}
    for f in entity.user_fields:
        py = _PY_TYPES.get(f.type, str)
        fields[f.name] = (py, ...) if f.required else (Optional[py], None)
    return create_model(_model_name(entity.name, "Create"), **fields)


def _make_replace_model(entity: EntityDef):
    """PUT body — no id, entity fields per their required flags."""
    fields: dict[str, Any] = {}
    for f in entity.user_fields:
        py = _PY_TYPES.get(f.type, str)
        fields[f.name] = (py, ...) if f.required else (Optional[py], None)
    return create_model(_model_name(entity.name, "Replace"), **fields)


def _make_patch_model(entity: EntityDef):
    """PATCH body — no id, all fields optional."""
    fields: dict[str, Any] = {
        f.name: (Optional[_PY_TYPES.get(f.type, str)], None)
        for f in entity.user_fields
    }
    return create_model(_model_name(entity.name, "Patch"), **fields)


def _make_bulk_request_model(entity: EntityDef, CreateModel):
    """POST /bulk body — {items: [CreateModel]}."""
    return create_model(
        _model_name(entity.name, "BulkRequest"),
        items=(list[CreateModel], ...),
    )


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce(value: Any, ftype: str) -> Any:
    if value is None:
        return None
    if ftype == "integer":
        return int(value)
    if ftype == "real":
        return float(value)
    return str(value)


def make_router(entity: EntityDef) -> APIRouter:
    table = entity.name
    router = APIRouter(prefix=f"/{table}", tags=[table])
    user_fields = entity.user_fields

    RecordModel = _make_record_model(entity)
    CreateModel = _make_create_model(entity)
    ReplaceModel = _make_replace_model(entity)
    PatchModel = _make_patch_model(entity)
    BulkRequestModel = _make_bulk_request_model(entity, CreateModel)

    def _row_to_dict(row) -> dict:
        return dict(row)

    def _fields_from_data(data: dict, partial: bool = False) -> dict:
        """Coerce validated data into DB-ready field dict (excludes id)."""
        result: dict = {}
        errors: list[str] = []
        for f in user_fields:
            if f.name not in data:
                if f.required and not partial:
                    errors.append(f"'{f.name}' is required")
                continue
            try:
                result[f.name] = _coerce(data[f.name], f.type)
            except (ValueError, TypeError):
                errors.append(f"'{f.name}' must be {f.type}")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
        return result

    # ── GET all ──────────────────────────────────────────────────────────────
    @router.get("", response_model=list[RecordModel])
    def list_records():
        with db() as conn:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── GET one ──────────────────────────────────────────────────────────────
    @router.get("/{record_id}", response_model=RecordModel, responses={**_404})
    def get_record(record_id: str):
        with db() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"'{record_id}' not found in {table}"
            )
        return _row_to_dict(row)

    # ── POST ─────────────────────────────────────────────────────────────────
    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=RecordModel,
        responses={**_AUTH_ERRORS, **_409},
        dependencies=[Depends(require_token)],
    )
    async def create_record(request_body: CreateModel):
        data = request_body.model_dump()
        record_id = data["id"]
        fields = _fields_from_data(data)
        now = utcnow()
        cols = ["id"] + list(fields.keys()) + ["updated_at"]
        vals = [str(record_id)] + list(fields.values()) + [now]
        placeholders = ",".join("?" * len(cols))
        with db() as conn:
            if conn.execute(
                f"SELECT id FROM {table} WHERE id = ?", (record_id,)
            ).fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"'{record_id}' already exists in {table}",
                )
            conn.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals
            )
        return {"id": record_id, **fields, "updated_at": now}

    # ── PUT ──────────────────────────────────────────────────────────────────
    @router.put(
        "/{record_id}",
        response_model=RecordModel,
        responses={**_AUTH_ERRORS, **_404},
        dependencies=[Depends(require_token)],
    )
    async def replace_record(record_id: str, request_body: ReplaceModel):
        fields = _fields_from_data(request_body.model_dump())
        now = utcnow()
        set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        vals = list(fields.values()) + [now, record_id]
        with db() as conn:
            result = conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?", vals
            )
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"'{record_id}' not found in {table}"
                )
        return {"id": record_id, **fields, "updated_at": now}

    # ── PATCH ─────────────────────────────────────────────────────────────────
    @router.patch(
        "/{record_id}",
        response_model=RecordModel,
        responses={**_AUTH_ERRORS, **_404},
        dependencies=[Depends(require_token)],
    )
    async def patch_record(record_id: str, request_body: PatchModel):
        with db() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=404, detail=f"'{record_id}' not found in {table}"
                )
            current = dict(row)
        fields = _fields_from_data(
            request_body.model_dump(exclude_unset=True), partial=True
        )
        if not fields:
            raise HTTPException(status_code=422, detail="No valid fields provided")
        now = utcnow()
        set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        vals = list(fields.values()) + [now, record_id]
        with db() as conn:
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", vals)
        return {**current, **fields, "updated_at": now}

    # ── DELETE ────────────────────────────────────────────────────────────────
    @router.delete(
        "/{record_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**_AUTH_ERRORS, **_404},
        dependencies=[Depends(require_token)],
    )
    def delete_record(record_id: str):
        with db() as conn:
            result = conn.execute(
                f"DELETE FROM {table} WHERE id = ?", (record_id,)
            )
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"'{record_id}' not found in {table}"
                )

    # ── POST /bulk ────────────────────────────────────────────────────────────
    @router.post(
        "/bulk",
        response_model=BulkResult,
        responses={**_AUTH_ERRORS},
        dependencies=[Depends(require_token)],
    )
    async def bulk_upsert(request_body: BulkRequestModel):
        items = [item.model_dump() for item in request_body.items]
        if len(items) > 5000:
            raise HTTPException(
                status_code=422, detail="Maximum 5 000 items per bulk request"
            )
        now = utcnow()
        inserted = updated = 0
        errors: list[str] = []
        with db() as conn:
            existing = {
                r[0] for r in conn.execute(f"SELECT id FROM {table}").fetchall()
            }
            for item in items:
                rid = item.get("id", "")
                if not rid:
                    errors.append("item missing 'id'")
                    continue
                try:
                    fields = _fields_from_data(item)
                except HTTPException as e:
                    errors.append(f"{rid}: {e.detail}")
                    continue
                if rid in existing:
                    set_clause = (
                        ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
                    )
                    conn.execute(
                        f"UPDATE {table} SET {set_clause} WHERE id = ?",
                        [*fields.values(), now, rid],
                    )
                    updated += 1
                else:
                    cols = ["id"] + list(fields.keys()) + ["updated_at"]
                    vals = [str(rid)] + list(fields.values()) + [now]
                    conn.execute(
                        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                        vals,
                    )
                    existing.add(rid)
                    inserted += 1
        return {
            "inserted": inserted,
            "updated": updated,
            "total": inserted + updated,
            "errors": errors,
        }

    return router
