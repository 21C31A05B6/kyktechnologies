"""db_sql.py — SQLAlchemy-backed store, used when DATABASE_URL is set.

Implements the exact same function signatures as db.py's JSON-file store
(read / write / insert / find / update / remove / now_iso), so app.py never
needs to know which backend is active — see db.py's dispatcher at the
bottom of this file's sibling module.

Design: rather than hand-writing a SQLAlchemy model per collection (jobs,
applications, talent, contacts, ...), every collection is stored as rows in
one generic `records` table: (collection, id, data JSON, created_at,
updated_at). This mirrors the JSON-file store's schema-less shape exactly,
so no data-migration mapping is needed beyond copying the JSON files in —
see migrate_json_to_sql.py. It works against PostgreSQL (recommended for
production — set DATABASE_URL to a postgresql:// URL and `pip install
psycopg2-binary`) or any other SQLAlchemy dialect, including SQLite, which
is what this module is exercised against in this environment since a live
Postgres server isn't reachable here.

Once you're ready to move a given collection (e.g. `jobs`) to a real typed
table with foreign keys and indexes, add a proper SQLAlchemy model for it
and route just that collection's read/insert/update/remove through it —
the generic table and the typed tables can coexist during the transition.
"""

import os
import threading
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    DateTime,
    create_engine,
    select,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from models import (
    Base as ModelsBase,
    User,
    Admin,
    Employee,
    HRManager,
    TeamLead,
    Recruiter,
    Client,
    ContentManager,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
_Session = sessionmaker(bind=_engine, future=True)
Base = declarative_base()
_lock = threading.Lock()


class Record(Base):
    __tablename__ = "records"

    collection = Column(String(64), primary_key=True)
    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


Base.metadata.create_all(_engine)
ModelsBase.metadata.create_all(_engine)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row):
    body = dict(row.data or {})
    body["id"] = row.id
    if row.created_at:
        body["createdAt"] = row.created_at.isoformat()
    if row.updated_at:
        body["updatedAt"] = row.updated_at.isoformat()
    return body


def read(collection):
    with _Session() as session:
        rows = session.scalars(
            select(Record).where(Record.collection == collection).order_by(Record.id)
        ).all()
        return [_row_to_dict(r) for r in rows]


def write(collection, rows):
    """Replace every row in a collection. Kept for interface parity with
    the JSON store; SQL callers should prefer insert/update/remove."""
    with _lock, _Session() as session:
        session.query(Record).filter(Record.collection == collection).delete()
        for row in rows:
            body = {k: v for k, v in row.items() if k not in ("id", "createdAt", "updatedAt")}
            session.add(
                Record(
                    collection=collection,
                    id=row.get("id"),
                    data=body,
                    created_at=datetime.now(timezone.utc),
                )
            )
        session.commit()


def _sync_user_insert_or_update(body):
    """Synchronize an account row with the users table and its role-specific table."""
    try:
        email = (body.get("email") or "").strip().lower()
        if not email:
            return
        name = body.get("name") or "User"
        role = body.get("role") or "viewer"
        pw_hash = body.get("passwordHash") or ""

        with _Session() as session:
            user = session.scalars(select(User).where(User.email == email)).first()
            role_changed = False
            if not user:
                user = User(
                    email=email,
                    password_hash=pw_hash,
                    name=name,
                    role=role,
                    status=body.get("status", "active"),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(user)
                session.flush()
            else:
                role_changed = user.role != role
                user.name = name
                user.role = role
                if "status" in body:
                    user.status = body.get("status") or user.status
                if pw_hash:
                    user.password_hash = pw_hash
                user.updated_at = datetime.now(timezone.utc)
                session.flush()

            # Fix: on a role change, delete every *other* role-specific
            # profile row for this user first, so switching Employee ->
            # HR Manager (for example) can't leave a stale `employees`
            # row behind alongside the new `hr_managers` row. This and
            # the role-table upsert below run in the same session/
            # transaction, so the old-profile-delete + new-profile-create
            # + users.role update commit atomically together.
            if role_changed:
                ROLE_TABLE_MAP = {
                    "super_admin": Admin, "employee": Employee, "hr_manager": HRManager,
                    "team_lead": TeamLead, "recruiter": Recruiter, "client": Client,
                    "content_manager": ContentManager,
                }
                for other_role, model in ROLE_TABLE_MAP.items():
                    if other_role == role:
                        continue
                    stale = session.scalars(select(model).where(model.user_id == user.id)).first()
                    if stale:
                        session.delete(stale)
                session.flush()

            # Synchronize role-specific table
            if role == "super_admin":
                adm = session.scalars(select(Admin).where(Admin.user_id == user.id)).first()
                if not adm:
                    session.add(Admin(user_id=user.id, name=name, email=email, is_super_admin=True, department="Executive"))
                else:
                    adm.name = name
                    adm.email = email
            elif role == "employee":
                emp = session.scalars(select(Employee).where(Employee.user_id == user.id)).first()
                if not emp:
                    code = f"KYK-EMP-{user.id:03d}"
                    session.add(Employee(user_id=user.id, employee_code=code, name=name, email=email, department="Software & Web Services", designation="Software Engineer"))
                else:
                    emp.name = name
                    emp.email = email
            elif role == "hr_manager":
                hr = session.scalars(select(HRManager).where(HRManager.user_id == user.id)).first()
                if not hr:
                    session.add(HRManager(user_id=user.id, name=name, email=email, department="Human Resources", office_location="Warangal, IN"))
                else:
                    hr.name = name
                    hr.email = email
            elif role == "team_lead":
                tl = session.scalars(select(TeamLead).where(TeamLead.user_id == user.id)).first()
                if not tl:
                    session.add(TeamLead(user_id=user.id, name=name, email=email, department="Software & Web Services", team_name="Core Engineering"))
                else:
                    tl.name = name
                    tl.email = email
            elif role == "recruiter":
                rec = session.scalars(select(Recruiter).where(Recruiter.user_id == user.id)).first()
                if not rec:
                    session.add(Recruiter(user_id=user.id, name=name, email=email, specialization="Technical & Global Sourcing"))
                else:
                    rec.name = name
                    rec.email = email
            elif role == "client":
                cl = session.scalars(select(Client).where(Client.user_id == user.id)).first()
                if not cl:
                    session.add(Client(user_id=user.id, client_name=name, company_name=name + " Corp", email=email))
                else:
                    cl.client_name = name
                    cl.email = email
            elif role == "content_manager":
                cm = session.scalars(select(ContentManager).where(ContentManager.user_id == user.id)).first()
                if not cm:
                    session.add(ContentManager(user_id=user.id, name=name, email=email, department="Marketing & Content"))
                else:
                    cm.name = name
                    cm.email = email

            session.commit()
    except Exception as e:
        print(f"Warning: error synchronizing user to separate table: {e}")


def _sync_user_remove(email):
    """Remove user from users table and cascades to role table."""
    try:
        if not email:
            return
        with _Session() as session:
            user = session.scalars(select(User).where(User.email == email.lower())).first()
            if user:
                session.delete(user)
                session.commit()
    except Exception as e:
        print(f"Warning: error removing user from separate table: {e}")


def insert(collection, row):
    with _lock, _Session() as session:
        next_id = (
            session.scalar(
                select(func.max(Record.id)).where(Record.collection == collection)
            )
            or 0
        ) + 1
        now = datetime.now(timezone.utc)
        body = {k: v for k, v in row.items() if k not in ("id", "createdAt", "updatedAt")}
        record = Record(collection=collection, id=next_id, data=body, created_at=now)
        session.add(record)
        session.commit()
        res = _row_to_dict(record)

    if collection == "admins":
        _sync_user_insert_or_update(body)

    return res


def find(collection, row_id):
    with _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        return _row_to_dict(row) if row else None


def update(collection, row_id, patch):
    with _lock, _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        if not row:
            return None
        body = dict(row.data or {})
        body.update({k: v for k, v in patch.items() if k not in ("id", "createdAt", "updatedAt")})
        row.data = body
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        res = _row_to_dict(row)

    if collection == "admins":
        _sync_user_insert_or_update(res)

    return res


def remove(collection, row_id):
    deleted_email = None
    with _lock, _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        if not row:
            return False
        if collection == "admins" and row.data:
            deleted_email = row.data.get("email")
        session.delete(row)
        session.commit()

    if collection == "admins" and deleted_email:
        _sync_user_remove(deleted_email)

    return True


# ─────────────────────────────────────────── Direct queries on separate tables

def get_users():
    with _Session() as session:
        rows = session.scalars(select(User).order_by(User.id)).all()
        return [u.to_dict() for u in rows]


def get_admins():
    with _Session() as session:
        rows = session.scalars(select(Admin).order_by(Admin.id)).all()
        return [a.to_dict() for a in rows]


def get_employees():
    with _Session() as session:
        rows = session.scalars(select(Employee).order_by(Employee.id)).all()
        return [e.to_dict() for e in rows]


def get_hr_managers():
    with _Session() as session:
        rows = session.scalars(select(HRManager).order_by(HRManager.id)).all()
        return [h.to_dict() for h in rows]


def get_team_leads():
    with _Session() as session:
        rows = session.scalars(select(TeamLead).order_by(TeamLead.id)).all()
        return [t.to_dict() for t in rows]


def get_recruiters():
    with _Session() as session:
        rows = session.scalars(select(Recruiter).order_by(Recruiter.id)).all()
        return [r.to_dict() for r in rows]


def get_clients():
    with _Session() as session:
        rows = session.scalars(select(Client).order_by(Client.id)).all()
        return [c.to_dict() for c in rows]


def get_content_managers():
    with _Session() as session:
        rows = session.scalars(select(ContentManager).order_by(ContentManager.id)).all()
        return [m.to_dict() for m in rows]
