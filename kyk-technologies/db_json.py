"""db_json.py — tiny JSON-file data store (replaces the old Node db.js).

Every "collection" is one file under /data, e.g. data/jobs.json.
Zero configuration, no database server. The function signatures are kept
small and isolated so this can be swapped for PostgreSQL/MongoDB later
without touching app.py's route logic much.
"""

import json
import os
import threading
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_lock = threading.Lock()


def _path(collection):
    return os.path.join(DATA_DIR, f"{collection}.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def read(collection):
    """Return every row in a collection (newest last)."""
    _ensure_dir()
    try:
        with open(_path(collection), "r", encoding="utf-8") as f:
            rows = json.load(f)
            return rows if isinstance(rows, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write(collection, rows):
    _ensure_dir()
    tmp = _path(collection) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _path(collection))


def insert(collection, row):
    """Insert a row, assigning an auto-incrementing id and createdAt."""
    with _lock:
        rows = read(collection)
        next_id = max([r.get("id", 0) for r in rows], default=0) + 1
        record = {"id": next_id, **row, "createdAt": now_iso()}
        rows.append(record)
        write(collection, rows)
        return record


def find(collection, row_id):
    for row in read(collection):
        if row.get("id") == row_id:
            return row
    return None


def update(collection, row_id, patch):
    """Merge `patch` into the row with this id. Returns the row or None."""
    with _lock:
        rows = read(collection)
        updated = None
        for i, row in enumerate(rows):
            if row.get("id") == row_id:
                updated = {**row, **patch, "id": row_id, "updatedAt": now_iso()}
                rows[i] = updated
                break
        if updated:
            write(collection, rows)
        return updated


def remove(collection, row_id):
    """Delete a row by id. Returns True if something was deleted."""
    with _lock:
        rows = read(collection)
        kept = [r for r in rows if r.get("id") != row_id]
        if len(kept) == len(rows):
            return False
        write(collection, kept)
        return True
