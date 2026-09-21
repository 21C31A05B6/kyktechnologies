"""db.py — storage dispatcher.

Zero configuration: with no DATABASE_URL set, every "collection" (jobs,
applications, talent, contacts, newsletter, insights, admins, audit_log)
lives in a JSON file under /data — see db_json.py. That's the demo/dev
path and needs nothing installed.

Production: set the DATABASE_URL environment variable to a SQLAlchemy
connection string (e.g. postgresql://user:pass@host:5432/kyk) and install
the driver — `pip install psycopg2-binary` for Postgres — and every read,
insert, update and remove call below transparently goes to db_sql.py's
SQLAlchemy-backed store instead. app.py and every route in it are
unchanged either way; they only ever call the five functions re-exported
here.

To migrate existing JSON data into a freshly-configured database, run:
    DATABASE_URL=postgresql://... python migrate_json_to_sql.py
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if os.environ.get("DATABASE_URL"):
    from db_sql import (  # noqa: F401
        read,
        write,
        insert,
        find,
        update,
        remove,
        now_iso,
        get_users,
        get_admins,
        get_employees,
        get_hr_managers,
        get_team_leads,
        get_recruiters,
        get_clients,
        get_content_managers,
    )
else:
    from db_json import read, write, insert, find, update, remove, now_iso  # noqa: F401

    def get_users():
        return read("admins")

    def get_admins():
        return [u for u in read("admins") if u.get("role") == "super_admin"]

    def get_employees():
        return [u for u in read("admins") if u.get("role") == "employee"]

    def get_hr_managers():
        return [u for u in read("admins") if u.get("role") == "hr_manager"]

    def get_team_leads():
        return [u for u in read("admins") if u.get("role") == "team_lead"]

    def get_recruiters():
        return [u for u in read("admins") if u.get("role") == "recruiter"]

    def get_clients():
        return [u for u in read("admins") if u.get("role") == "client"]

    def get_content_managers():
        return [u for u in read("admins") if u.get("role") == "content_manager"]

