import json
import os
from dataclasses import dataclass

ALLOWED_TYPES = {"text", "real", "integer"}


@dataclass
class FieldDef:
    name: str
    type: str       # text | real | integer
    required: bool


@dataclass
class EntityDef:
    name: str
    fields: list[FieldDef]

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]

    @property
    def user_fields(self) -> list[FieldDef]:
        return [f for f in self.fields if f.name != "id"]


def load_schema(path: str = "schema.json") -> list[EntityDef]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"schema.json not found at {path}")

    with open(path) as fh:
        raw = json.load(fh)

    entities: list[EntityDef] = []
    for entry in raw:
        name = entry["name"].strip().lower()
        fields: list[FieldDef] = []
        seen = set()
        has_id = False
        for f in entry["fields"]:
            fname = f["name"].strip().lower()
            ftype = f["type"].strip().lower()
            if ftype not in ALLOWED_TYPES:
                raise ValueError(f"Entity '{name}': field '{fname}' has unsupported type '{ftype}'. Use: {ALLOWED_TYPES}")
            if fname in seen:
                raise ValueError(f"Entity '{name}': duplicate field '{fname}'")
            seen.add(fname)
            if fname == "id":
                has_id = True
            fields.append(FieldDef(name=fname, type=ftype, required=f.get("required", False)))
        if not has_id:
            raise ValueError(f"Entity '{name}' must have an 'id' field")
        entities.append(EntityDef(name=name, fields=fields))

    return entities
