"""SQLite layer: schema init + all DB helper functions. No ORM, raw sqlite3."""
import os
import sqlite3
from contextlib import contextmanager

from config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    context           TEXT DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    raw_text    TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'text',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    note_id     INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    category    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conflicts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id        INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    note_id          INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    existing_fact_id INTEGER NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    new_key          TEXT NOT NULL,
    new_value        TEXT NOT NULL,
    category         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    resolution_note  TEXT DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at      TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_person ON notes(person_id);
CREATE INDEX IF NOT EXISTS idx_facts_person ON facts(person_id);
CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(person_id, key, is_active);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status);
"""


@contextmanager
def get_connection():
    """Yield a sqlite3 connection with Row factory + FK enforcement.
    Commits on success, rolls back on exception."""
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _rows_to_list(rows):
    return [dict(r) for r in rows]


# ----------------------------- People -----------------------------

def list_people():
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT p.*, MAX(n.created_at) AS last_note_at,
                      (SELECT COUNT(*) FROM conflicts c
                       WHERE c.person_id = p.id AND c.status = 'pending') AS pending_conflicts
               FROM people p
               LEFT JOIN notes n ON n.person_id = p.id
               GROUP BY p.id
               ORDER BY p.name COLLATE NOCASE""").fetchall()
        return _rows_to_list(rows)


def create_person(name, relationship_type, context=""):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO people (name, relationship_type, context) VALUES (?,?,?)",
            (name, relationship_type, context))
        new_id = cur.lastrowid
    return get_person(new_id)


def get_person(person_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
        return _row_to_dict(row)


def update_person(person_id, name=None, relationship_type=None, context=None):
    fields, params = [], []
    if name is not None:
        fields.append("name=?"); params.append(name)
    if relationship_type is not None:
        fields.append("relationship_type=?"); params.append(relationship_type)
    if context is not None:
        fields.append("context=?"); params.append(context)
    if not fields:
        return get_person(person_id)
    fields.append("updated_at=datetime('now')")
    params.append(person_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE people SET {', '.join(fields)} WHERE id=?", params)
    return get_person(person_id)


def delete_person(person_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM people WHERE id=?", (person_id,))


# ----------------------------- Notes -----------------------------

def insert_note(person_id, raw_text, source="text"):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO notes (person_id, raw_text, source) VALUES (?,?,?)",
            (person_id, raw_text, source))
        return cur.lastrowid


def list_notes(person_id, limit=None):
    with get_connection() as conn:
        sql = "SELECT * FROM notes WHERE person_id=? ORDER BY created_at DESC, id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, (person_id,)).fetchall()
        return _rows_to_list(rows)


def delete_note(note_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))


# ----------------------------- Facts -----------------------------

def insert_fact(person_id, note_id, category, key, value):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO facts (person_id, note_id, category, key, value)
               VALUES (?,?,?,?,?)""",
            (person_id, note_id, category, key, value))
        return cur.lastrowid


def get_active_fact_by_key(person_id, key):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facts WHERE person_id=? AND key=? AND is_active=1",
            (person_id, key)).fetchone()
        return _row_to_dict(row)


def get_active_facts(person_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM facts WHERE person_id=? AND is_active=1
               ORDER BY category, key""", (person_id,)).fetchall()
        return _rows_to_list(rows)


def update_fact_value(fact_id, value):
    with get_connection() as conn:
        conn.execute(
            "UPDATE facts SET value=?, updated_at=datetime('now') WHERE id=?",
            (value, fact_id))


def deactivate_fact(fact_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE facts SET is_active=0, updated_at=datetime('now') WHERE id=?",
            (fact_id,))


def get_fact(fact_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        return _row_to_dict(row)


# ----------------------------- Conflicts -----------------------------

def insert_conflict(person_id, note_id, existing_fact_id, new_key, new_value, category):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO conflicts
               (person_id, note_id, existing_fact_id, new_key, new_value, category)
               VALUES (?,?,?,?,?,?)""",
            (person_id, note_id, existing_fact_id, new_key, new_value, category))
        return cur.lastrowid


def list_conflicts(person_id=None, status="pending"):
    with get_connection() as conn:
        sql = """SELECT c.*, p.name AS person_name, f.value AS existing_value
                 FROM conflicts c
                 JOIN people p ON p.id = c.person_id
                 JOIN facts f ON f.id = c.existing_fact_id
                 WHERE c.status = ?"""
        params = [status]
        if person_id is not None:
            sql += " AND c.person_id = ?"
            params.append(person_id)
        sql += " ORDER BY c.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return _rows_to_list(rows)


def count_pending_conflicts():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM conflicts WHERE status='pending'").fetchone()
        return row["n"]


def get_conflict(conflict_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM conflicts WHERE id=?", (conflict_id,)).fetchone()
        return _row_to_dict(row)


def mark_conflict_resolved(conflict_id, status, resolution_note=""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE conflicts
               SET status=?, resolution_note=?, resolved_at=datetime('now')
               WHERE id=?""",
            (status, resolution_note, conflict_id))


# ----------------------------- Aggregates for AI -----------------------------

def all_people_with_facts():
    """Condensed snapshot of everyone + their active facts, for global Q&A."""
    people = list_people()
    out = []
    for p in people:
        out.append({
            "id": p["id"],
            "name": p["name"],
            "relationship_type": p["relationship_type"],
            "facts": get_active_facts(p["id"]),
        })
    return out
