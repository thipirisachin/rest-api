import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from app.db import init_db
from app.schema import load_schema, EntityDef, FieldDef, ALLOWED_TYPES
from app.dynamic_routes import make_router
from app.auth import require_token


class HealthResponse(BaseModel):
    status: str


class FieldResponse(BaseModel):
    name: str
    type: str
    required: bool


class EntityResponse(BaseModel):
    name: str
    fields: list[FieldResponse]


class FieldInput(BaseModel):
    name: str
    type: str = "text"
    required: bool = False


class CreateTableRequest(BaseModel):
    name: str
    fields: list[FieldInput]


_AUTH_ERRORS = {
    401: {"description": "Invalid or missing bearer token"},
    500: {"description": "API_TOKEN not configured"},
}

SCHEMA_PATH = "schema.json"

entities: list[EntityDef] = load_schema(SCHEMA_PATH) if os.path.exists(SCHEMA_PATH) else []

app = FastAPI(title="Local REST API", version="1.0.0")

for entity in entities:
    app.include_router(make_router(entity))

app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")


@app.on_event("startup")
def startup():
    init_db(entities)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/index.html")


@app.get("/health", tags=["meta"], response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/schema", tags=["meta"], response_model=list[EntityResponse])
def get_schema():
    return JSONResponse([
        {
            "name": e.name,
            "fields": [{"name": f.name, "type": f.type, "required": f.required} for f in e.fields],
        }
        for e in entities
    ])


@app.post("/tables", tags=["meta"], response_model=EntityResponse,
          responses={**_AUTH_ERRORS, 409: {"description": "Table already exists"}},
          dependencies=[Depends(require_token)])
def create_table(body: CreateTableRequest):
    name = body.name.strip().lower()
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        raise HTTPException(status_code=422, detail="Table name must start with a letter and contain only letters, digits, underscores")

    if any(e.name == name for e in entities):
        raise HTTPException(status_code=409, detail=f"Table '{name}' already exists")

    if not body.fields:
        raise HTTPException(status_code=422, detail="'fields' must be a non-empty array")

    field_defs: list[FieldDef] = []
    seen = set()
    has_id = False
    for f in body.fields:
        fname = f.name.strip().lower()
        ftype = f.type.strip().lower()
        frequired = f.required
        if not fname:
            raise HTTPException(status_code=422, detail="Each field must have a name")
        if fname in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate field name '{fname}'")
        if ftype not in ALLOWED_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid type '{ftype}' for field '{fname}'. Use: text, real, integer")
        seen.add(fname)
        if fname == "id":
            has_id = True
        field_defs.append(FieldDef(name=fname, type=ftype, required=frequired))

    if not has_id:
        raise HTTPException(status_code=422, detail="Table must include an 'id' field")

    new_entity = EntityDef(name=name, fields=field_defs)

    init_db([new_entity])
    app.include_router(make_router(new_entity))
    app.openapi_schema = None  # bust cached OpenAPI doc

    entities.append(new_entity)

    # persist back to schema.json
    with open(SCHEMA_PATH, "w") as fh:
        json.dump([
            {"name": e.name, "fields": [{"name": f.name, "type": f.type, "required": f.required} for f in e.fields]}
            for e in entities
        ], fh, indent=2)

    return {
        "name": name,
        "fields": [{"name": f.name, "type": f.type, "required": f.required} for f in field_defs],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3333))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
