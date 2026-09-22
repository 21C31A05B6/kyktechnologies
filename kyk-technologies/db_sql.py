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
import time
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
    delete,
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
    Job,
    Application,
    AttendanceRecord,
    AuditLog,
    SessionRecord,
)

# No live credentials are hardcoded here. If DATABASE_URL isn't set in the
# environment, fall back to a local SQLite file rather than any real server.
DATABASE_URL = (os.environ.get("DATABASE_URL") or "sqlite:///kyk_fallback.db").strip().strip("'\"")
# Render and other PaaS providers supply 'postgres://' which SQLAlchemy 1.4+ rejects
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    if not DATABASE_URL or "://" not in DATABASE_URL:
        raise ValueError(f"Empty or invalid DATABASE_URL: {DATABASE_URL!r}")
    # Pool tuned for 2 Gunicorn workers × 4 threads = 8 concurrent sessions.
    # pool_size=10 keeps connections warm; max_overflow=5 allows short bursts
    # up to 15 total connections without raising PoolTimeout under load.
    _engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,   # recycle connections every 30 min to avoid stale sockets
    )
except Exception as e:
    print(f"Warning: Failed to create SQLAlchemy engine with '{DATABASE_URL}': {e}. Using fallback SQLite engine.")
    _engine = create_engine("sqlite:///kyk_fallback.db", future=True)

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


def init_db():
    """Create database tables if they do not exist."""
    try:
        Base.metadata.create_all(_engine)
        ModelsBase.metadata.create_all(_engine)
    except Exception as e:
        print(f"Warning: Database table creation failed: {e}")


init_db()


def health_check():
    """Verify that the configured SQL database accepts a real query."""
    from sqlalchemy import text
    with _engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"backend": "sql", "database": "reachable"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# Session operations use the indexed sessions table directly. Authentication is
# a hot path, so scanning and deserialising every active session does not scale.
def get_session_by_jti(jti):
    with _Session() as session:
        row = session.scalar(select(SessionRecord).where(SessionRecord.jti == jti))
        return row.to_dict() if row else None


def create_session(owner_type, owner_id, jti, max_sessions, ip="", ua="", exp=0):
    """Create a session and retain only the newest sessions for its owner."""
    with _Session() as session:
        session.execute(delete(SessionRecord).where(SessionRecord.exp < int(time.time())))
        existing = session.scalars(
            select(SessionRecord)
            .where(SessionRecord.owner_type == owner_type,
                   SessionRecord.owner_id == owner_id)
            .order_by(SessionRecord.created_at, SessionRecord.id)
        ).all()
        for stale in existing[:max(0, len(existing) - max_sessions + 1)]:
            session.delete(stale)
        session.add(SessionRecord(
            jti=jti, owner_type=owner_type, owner_id=owner_id,
            ip=ip, ua=ua[:200], exp=int(exp or 0),
        ))
        session.commit()


def revoke_session(jti):
    with _Session() as session:
        session.execute(delete(SessionRecord).where(SessionRecord.jti == jti))
        session.commit()


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
        if collection == "jobs":
            try:
                jobs = session.scalars(select(Job).order_by(Job.id)).all()
                if jobs:
                    return [j.to_dict() for j in jobs]
            except Exception:
                pass
        elif collection == "applications":
            try:
                apps = session.scalars(select(Application).order_by(Application.id.desc())).all()
                if apps:
                    return [a.to_dict() for a in apps]
            except Exception:
                pass
        elif collection == "attendance":
            try:
                atts = session.scalars(select(AttendanceRecord).order_by(AttendanceRecord.id)).all()
                if atts:
                    return [att.to_dict() for att in atts]
            except Exception:
                pass
        elif collection == "audit_log":
            try:
                logs = session.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all()
                if logs:
                    return [l.to_dict() for l in logs]
            except Exception:
                pass
        elif collection == "sessions":
            try:
                sess = session.scalars(select(SessionRecord).order_by(SessionRecord.id)).all()
                if sess:
                    return [s.to_dict() for s in sess]
            except Exception:
                pass

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
                    session.add(Employee(
                        user_id=user.id,
                        employee_code=code,
                        name=name,
                        email=email,
                        phone=body.get("phone"),
                        department=body.get("department", "Software & Web Services"),
                        designation=body.get("designation", "Software Engineer"),
                        status=body.get("status", "active"),
                    ))
                else:
                    emp.name = name
                    emp.email = email
                    if "phone" in body:
                        emp.phone = body.get("phone")
                    if "status" in body:
                        emp.status = body.get("status") or emp.status
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

    # Synchronize to dedicated typed tables
    try:
        if collection == "jobs":
            with _Session() as session:
                job = Job(
                    id=next_id,
                    title=row.get("title", ""),
                    department=row.get("department", ""),
                    location=row.get("location", ""),
                    type=row.get("type", "Full-time"),
                    level=row.get("level", "Mid-level"),
                    description=row.get("description", ""),
                    requirements=row.get("requirements", []),
                    active=bool(row.get("active", True)),
                    created_at=now,
                    updated_at=now,
                )
                session.merge(job)
                session.commit()
        elif collection == "applications":
            with _Session() as session:
                app = Application(
                    id=next_id,
                    job_id=row.get("jobId"),
                    job_title=row.get("jobTitle"),
                    name=row.get("name", ""),
                    email=row.get("email", ""),
                    phone=row.get("phone", ""),
                    status=row.get("status", "applied"),
                    notes=row.get("notes", ""),
                    resume_filename=row.get("resumeFilename", ""),
                    created_at=now,
                    updated_at=now,
                )
                session.merge(app)
                session.commit()
        elif collection == "attendance":
            with _Session() as session:
                att = AttendanceRecord(
                    id=next_id,
                    user_id=row.get("adminId"),
                    user_name=row.get("adminName"),
                    user_email=row.get("adminEmail"),
                    user_role=row.get("adminRole"),
                    date=str(row.get("date", "")),
                    check_in=row.get("checkIn"),
                    check_out=row.get("checkOut"),
                    worked_seconds=int(row.get("workedSeconds") or 0),
                    day_status=row.get("dayStatus", "present"),
                    created_at=now,
                    updated_at=now,
                )
                session.merge(att)
                session.commit()
        elif collection == "audit_log":
            with _Session() as session:
                log = AuditLog(
                    id=next_id,
                    admin_id=row.get("adminId"),
                    admin_email=row.get("adminEmail"),
                    admin_role=row.get("adminRole"),
                    action=row.get("action", ""),
                    detail=row.get("detail", ""),
                    ip=row.get("ip", ""),
                    created_at=now,
                )
                session.merge(log)
                session.commit()
        elif collection == "sessions":
            with _Session() as session:
                sess = SessionRecord(
                    id=next_id,
                    jti=row.get("jti", ""),
                    owner_type=row.get("owner_type", "user"),
                    owner_id=row.get("owner_id", 0),
                    ip=row.get("ip", ""),
                    ua=row.get("ua", ""),
                    exp=int(row.get("exp") or 0),
                    created_at=now,
                )
                session.merge(sess)
                session.commit()
        elif collection in ("admins", "users"):
            _sync_user_insert_or_update(body)
    except Exception as e:
        print(f"Warning: error synchronizing {collection} insert to dedicated table: {e}")

    return res


def find(collection, row_id):
    with _Session() as session:
        if collection == "jobs":
            try:
                job = session.get(Job, row_id)
                if job:
                    return job.to_dict()
            except Exception:
                pass
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

    # Synchronize to dedicated typed tables
    try:
        if collection == "jobs":
            with _Session() as session:
                job = session.get(Job, row_id)
                if job:
                    if "title" in patch: job.title = patch["title"]
                    if "department" in patch: job.department = patch["department"]
                    if "location" in patch: job.location = patch["location"]
                    if "type" in patch: job.type = patch["type"]
                    if "level" in patch: job.level = patch["level"]
                    if "description" in patch: job.description = patch["description"]
                    if "requirements" in patch: job.requirements = patch["requirements"]
                    if "active" in patch: job.active = bool(patch["active"])
                    job.updated_at = datetime.now(timezone.utc)
                    session.commit()
        elif collection == "applications":
            with _Session() as session:
                app = session.get(Application, row_id)
                if app:
                    if "status" in patch: app.status = patch["status"]
                    if "notes" in patch: app.notes = patch["notes"]
                    app.updated_at = datetime.now(timezone.utc)
                    session.commit()
        elif collection == "attendance":
            with _Session() as session:
                att = session.get(AttendanceRecord, row_id)
                if att:
                    if "checkOut" in patch: att.check_out = patch["checkOut"]
                    if "workedSeconds" in patch: att.worked_seconds = int(patch["workedSeconds"] or 0)
                    if "dayStatus" in patch: att.day_status = patch["dayStatus"]
                    att.updated_at = datetime.now(timezone.utc)
                    session.commit()
        elif collection in ("admins", "users"):
            _sync_user_insert_or_update(res)
    except Exception as e:
        print(f"Warning: error synchronizing {collection} update to dedicated table: {e}")

    return res


def remove(collection, row_id):
    deleted_email = None
    with _lock, _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        if not row:
            return False
        if collection in ("admins", "users") and row.data:
            deleted_email = row.data.get("email")
        session.delete(row)
        session.commit()

    try:
        if collection == "jobs":
            with _Session() as session:
                job = session.get(Job, row_id)
                if job:
                    session.delete(job)
                    session.commit()
        elif collection == "applications":
            with _Session() as session:
                app = session.get(Application, row_id)
                if app:
                    session.delete(app)
                    session.commit()
        elif collection == "sessions":
            with _Session() as session:
                sess = session.get(SessionRecord, row_id)
                if sess:
                    session.delete(sess)
                    session.commit()
        elif collection in ("admins", "users") and deleted_email:
            _sync_user_remove(deleted_email)
    except Exception as e:
        print(f"Warning: error removing {collection} from dedicated table: {e}")

    return True


def record_login(identifier, role=None, ip=""):
    """Update last_login_at, last_login_ip, and increment login_count in users/admins tables."""
    now = datetime.now(timezone.utc)
    try:
        with _Session() as session:
            user = None
            if isinstance(identifier, int):
                user = session.scalars(select(User).where(User.id == identifier)).first()
            if not user:
                user = session.scalars(select(User).where(User.email == str(identifier).strip().lower())).first()
            if user:
                user.last_login_at = now
                user.last_login_ip = ip or user.last_login_ip
                user.login_count = (user.login_count or 0) + 1

                admin = session.scalars(select(Admin).where(Admin.user_id == user.id)).first()
                if admin:
                    admin.last_login_at = now
                    admin.last_login_ip = ip or admin.last_login_ip
                    admin.login_count = (admin.login_count or 0) + 1
            session.commit()
    except Exception as e:
        print(f"Warning: error recording login in users/admins: {e}")


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
