"""
Screening store — SQLite.

SIH26004 asks for a "digital patient record", "secure patient data management"
and an "analytics dashboard". Records arrive from the field app, which writes
them to IndexedDB first and pushes them here whenever a network appears, so
writes are idempotent on the client-generated id.

Patient names are the only free-text identifier kept; nothing here should be
treated as a de-identified dataset. Deployments handling real patients need
encryption at rest and access control on top of this.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get(
    "SCREENINGS_DB",
    os.path.join(os.path.dirname(__file__), "screenings.db"),
)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS screenings (
                id           TEXT PRIMARY KEY,
                created_at   TEXT NOT NULL,
                synced_at    TEXT NOT NULL,
                name         TEXT,
                age          INTEGER,
                sex          TEXT,
                village      TEXT,
                occupation   TEXT,
                symptom_total INTEGER,
                symptom_band TEXT,
                risk         REAL,
                band         TEXT,
                worse_knee   TEXT,
                payload      TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_band ON screenings(band)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_village ON screenings(village)")


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def upsert(record: dict) -> str:
    """Insert or replace by client id — a retried sync must not duplicate."""
    patient = record.get("patient") or {}
    prediction = (record.get("result") or {}).get("prediction") or {}
    worse = prediction.get("worse_knee") or {}

    row = (
        record.get("id"),
        record.get("createdAt") or datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat(),
        patient.get("name"),
        _as_int(patient.get("age")),
        patient.get("sex"),
        patient.get("village"),
        patient.get("occupation"),
        _as_int(record.get("symptomTotal")),
        record.get("symptomBand"),
        prediction.get("risk"),
        prediction.get("band"),
        worse.get("side"),
        json.dumps(record, ensure_ascii=False),
    )
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO screenings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    return record.get("id")


def list_screenings(limit: int = 500) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, created_at, name, age, sex, village, occupation,"
            " symptom_total, symptom_band, risk, band, worse_knee"
            " FROM screenings ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def summary() -> dict:
    """Counts the dashboard needs, computed in SQL rather than in the client."""
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]
        bands = {
            r["band"] or "unknown": r["n"]
            for r in c.execute(
                "SELECT band, COUNT(*) AS n FROM screenings GROUP BY band"
            ).fetchall()
        }
        villages = [
            dict(r)
            for r in c.execute(
                "SELECT COALESCE(NULLIF(village,''),'—') AS village,"
                " COUNT(*) AS n,"
                " SUM(CASE WHEN band='elevated' THEN 1 ELSE 0 END) AS elevated"
                " FROM screenings GROUP BY village ORDER BY n DESC LIMIT 12"
            ).fetchall()
        ]
        avg_age = c.execute(
            "SELECT AVG(age) FROM screenings WHERE age IS NOT NULL"
        ).fetchone()[0]
    return {
        "total": total,
        "bands": bands,
        "villages": villages,
        "mean_age": round(avg_age, 1) if avg_age else None,
    }
