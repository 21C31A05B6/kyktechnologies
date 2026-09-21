"""migrate_json_to_sql.py — copy existing /data/*.json rows into the
database named by DATABASE_URL, preserving ids.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/kyk python migrate_json_to_sql.py

Safe to re-run: existing rows in the target database are left as-is and
only missing ids are inserted, so running it twice won't duplicate data.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL before running this script, e.g.\n"
              "  DATABASE_URL=postgresql://user:pass@host:5432/kyk python migrate_json_to_sql.py")

import db_json
import db_sql

COLLECTIONS = [
    "jobs", "applications", "talent", "contacts",
    "newsletter", "insights", "admins", "audit_log", "attendance",
]


def main():
    total = 0
    for collection in COLLECTIONS:
        rows = db_json.read(collection)
        if not rows:
            continue
        existing_ids = {r["id"] for r in db_sql.read(collection)}
        moved = 0
        for row in rows:
            if row["id"] in existing_ids:
                continue
            with db_sql._lock, db_sql._Session() as session:
                body = {k: v for k, v in row.items() if k not in ("id", "createdAt", "updatedAt")}
                from datetime import datetime, timezone
                created = row.get("createdAt")
                created_dt = datetime.fromisoformat(created) if created else datetime.now(timezone.utc)
                session.add(db_sql.Record(collection=collection, id=row["id"], data=body, created_at=created_dt))
                session.commit()
            moved += 1
        print(f"{collection}: migrated {moved} of {len(rows)} row(s) ({len(rows) - moved} already present).")
        total += moved
    print(f"Done. {total} row(s) migrated in total.")


if __name__ == "__main__":
    main()
