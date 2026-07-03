import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_URL", "./data.db")

TYPE_MAP = {"text": "TEXT", "real": "REAL", "integer": "INTEGER"}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(entities) -> None:
    with db() as conn:
        for entity in entities:
            col_defs = ["id TEXT PRIMARY KEY"]
            for f in entity.user_fields:
                sql_type = TYPE_MAP.get(f.type, "TEXT")
                null_clause = "NOT NULL" if f.required else ""
                col_defs.append(f"{f.name} {sql_type} {null_clause}".strip())
            col_defs.append("updated_at TEXT NOT NULL")
            ddl = f"CREATE TABLE IF NOT EXISTS {entity.name} ({', '.join(col_defs)})"
            conn.execute(ddl)
