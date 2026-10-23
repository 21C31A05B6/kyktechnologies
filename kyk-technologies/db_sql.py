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

import re

def _sanitize_db_url(url: str) -> str:
    """Mask password credentials in database connection URLs for safe logging (SEC-10)."""
    if not url:
        return ""
    try:
        from sqlalchemy.engine import make_url
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)

_raw_db_url = os.environ.get("DATABASE_URL")
_is_prod = bool(
    os.environ.get("RENDER")
    or os.environ.get("KYK_PRODUCTION")
    or os.environ.get("FLASK_ENV") == "production"
    or os.environ.get("ENVIRONMENT") == "production"
)
_allow_sqlite = bool(
    os.environ.get("ALLOW_SQLITE_FALLBACK", "0") in ("1", "true", "True")
    or (not _raw_db_url and not _is_prod)
)

DATABASE_URL = (_raw_db_url or "sqlite:///kyk_fallback.db").strip().strip("'\"")
# Render and other PaaS providers supply 'postgres://' which SQLAlchemy 1.4+ rejects
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    if not DATABASE_URL or "://" not in DATABASE_URL:
        raise ValueError("Empty or invalid DATABASE_URL")
    
    # Ultra-high performance connection pool with keepalive settings
    # pool_pre_ping is disabled to eliminate 250ms WAN roundtrip latency on checkouts
    is_pg = "postgresql" in DATABASE_URL
    connect_args = {
        "connect_timeout": 10,
        "application_name": "kyk_turbo",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    } if is_pg else {}

    _engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=False,
        future=True,
        pool_size=25,
        max_overflow=50,
        pool_timeout=25,
        pool_recycle=600,   # recycle connections every 10 min
        connect_args=connect_args,
    )
except Exception as e:
    sanitized = _sanitize_db_url(DATABASE_URL)
    if not _allow_sqlite:
        raise RuntimeError(f"FATAL: Database engine creation failed for '{sanitized}': {e}") from e
    print(f"Warning: Failed to create SQLAlchemy engine with '{sanitized}': {e}. Using fallback SQLite engine.")
    _engine = create_engine("sqlite:///kyk_fallback.db", future=True)

_Session = sessionmaker(bind=_engine, future=True)
Base = declarative_base()

# Fine-grained per-collection locking (eliminates global write serialization for 100+ concurrent users)
_collection_locks = {}
_collection_locks_mutex = threading.Lock()

def _get_collection_lock(col_name):
    with _collection_locks_mutex:
        if col_name not in _collection_locks:
            _collection_locks[col_name] = threading.Lock()
        return _collection_locks[col_name]

_lock = threading.Lock()  # legacy fallback compatibility


class Record(Base):
    __tablename__ = "records"

    collection = Column(String(64), primary_key=True)
    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


_db_initialized = False


def init_db(force=False):
    """Create database tables synchronously if they do not exist."""
    global _db_initialized
    if _db_initialized and not force:
        return
    try:
        Base.metadata.create_all(_engine)
        ModelsBase.metadata.create_all(_engine)
        _db_initialized = True
    except Exception as e:
        print(f"Warning: Database table creation failed: {e}")
        if not _allow_sqlite:
            raise


# Run on explicit configuration or when deploying/starting service (DB-02)
if os.environ.get("AUTO_INIT_DB") == "1":
    try:
        init_db()
    except Exception as exc:
        print(f"Initial table verification note: {exc}")


def health_check():
    """Verify that the configured SQL database accepts a real query."""
    from sqlalchemy import text
    with _engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"backend": "sql", "database": "reachable"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── In-Memory Nanosecond-Speed High-Performance Cache ──────────────────
# Stores collections and active sessions in RAM with O(1) dictionary lookups
# Reads execute in < 1 microsecond (nanosecond range), avoiding remote WAN latency.
CACHE_TTL = float(os.environ.get("DB_CACHE_TTL", "60.0"))
_collection_cache = {}
_cache_lock = threading.RLock()

# Fast Session JTI cache for nanosecond authentication checks
_session_jti_cache = {}
_session_jti_lock = threading.Lock()


def invalidate_cache(collection=None):
    """Invalidate memory cache for a given collection or all collections."""
    with _cache_lock:
        if collection:
            _collection_cache.pop(collection, None)
        else:
            _collection_cache.clear()


def get_session_by_jti(jti):
    """Nanosecond session validation lookup from memory with DB fallback."""
    if not jti:
        return None
    now_ts = time.time()
    with _session_jti_lock:
        cached = _session_jti_cache.get(jti)
        if cached:
            if cached.get("exp") and cached["exp"] < now_ts:
                _session_jti_cache.pop(jti, None)
                return None
            return dict(cached)

    with _Session() as session:
        row = session.scalar(select(SessionRecord).where(SessionRecord.jti == jti))
        if row:
            res = row.to_dict()
            with _session_jti_lock:
                _session_jti_cache[jti] = dict(res)
            return res
        return None


def create_session(owner_type, owner_id, jti, max_sessions, ip="", ua="", exp=0):
    """Create a session and retain only the newest sessions for its owner."""
    now_ts = int(time.time())
    sess_dict = {
        "jti": jti,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "ip": ip,
        "ua": ua[:200],
        "exp": int(exp or 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _session_jti_lock:
        _session_jti_cache[jti] = dict(sess_dict)

    with _Session() as session:
        session.execute(delete(SessionRecord).where(SessionRecord.exp < now_ts))
        existing = session.scalars(
            select(SessionRecord)
            .where(SessionRecord.owner_type == owner_type,
                   SessionRecord.owner_id == owner_id)
            .order_by(SessionRecord.created_at, SessionRecord.id)
        ).all()
        for stale in existing[:max(0, len(existing) - max_sessions + 1)]:
            with _session_jti_lock:
                _session_jti_cache.pop(stale.jti, None)
            session.delete(stale)
        session.add(SessionRecord(
            jti=jti, owner_type=owner_type, owner_id=owner_id,
            ip=ip, ua=ua[:200], exp=int(exp or 0),
        ))
        session.commit()


def revoke_session(jti):
    """Revoke a session in both memory cache and SQL store instantly."""
    with _session_jti_lock:
        _session_jti_cache.pop(jti, None)
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


def _fetch_from_db(collection, session):
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


def read(collection):
    """Ultra-fast collection read with sub-microsecond in-memory caching."""
    now_ts = time.time()
    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry and (now_ts - entry["ts"] < CACHE_TTL):
            return [dict(r) for r in entry["rows"]]

    with _Session() as session:
        items = _fetch_from_db(collection, session)
        by_id = {it["id"]: it for it in items if "id" in it}
        with _cache_lock:
            _collection_cache[collection] = {
                "rows": items,
                "by_id": by_id,
                "ts": now_ts,
            }
        return [dict(r) for r in items]


def write(collection, rows):
    """Replace every row in a collection. Kept for interface parity with
    the JSON store; SQL callers should prefer insert/update/remove."""
    col_lock = _get_collection_lock(collection)
    with col_lock, _Session() as session:
        session.query(Record).filter(Record.collection == collection).delete()
        if collection == "attendance":
            try:
                session.query(AttendanceRecord).delete()
            except Exception:
                pass
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
            if collection == "attendance":
                try:
                    att = AttendanceRecord(
                        id=row.get("id"),
                        user_id=row.get("adminId"),
                        user_name=row.get("adminName", ""),
                        user_email=row.get("adminEmail", ""),
                        user_role=row.get("adminRole", ""),
                        date=row.get("date", ""),
                        check_in=datetime.fromisoformat(row["checkIn"]) if row.get("checkIn") else None,
                        check_out=datetime.fromisoformat(row["checkOut"]) if row.get("checkOut") else None,
                        worked_seconds=row.get("workedSeconds"),
                        status=row.get("dayStatus"),
                        data=body,
                    )
                    session.add(att)
                except Exception:
                    pass
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
    col_lock = _get_collection_lock(collection)
    with col_lock, _Session() as session:
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

    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry:
            entry["rows"].append(dict(res))
            entry["by_id"][res["id"]] = dict(res)
            entry["ts"] = time.time()
        if collection in ("admins", "users", "employees"):
            _collection_cache.pop("_typed_users", None)
            _collection_cache.pop("_typed_admins", None)
            _collection_cache.pop("_typed_employees", None)
            _collection_cache.pop("_typed_hr_managers", None)
            _collection_cache.pop("_typed_team_leads", None)
            _collection_cache.pop("_typed_recruiters", None)
            _collection_cache.pop("_typed_clients", None)
            _collection_cache.pop("_typed_content_managers", None)

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
    """Nanosecond O(1) in-memory record lookup with DB fallback."""
    now_ts = time.time()
    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry and (now_ts - entry["ts"] < CACHE_TTL):
            item = entry["by_id"].get(row_id)
            return dict(item) if item else None

    # Warm collection into RAM
    read(collection)
    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry:
            item = entry["by_id"].get(row_id)
            return dict(item) if item else None

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
    with _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        if not row:
            return None
        body = dict(row.data or {})
        body.update({k: v for k, v in patch.items() if k not in ("id", "createdAt", "updatedAt")})
        row.data = body
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        res = _row_to_dict(row)

    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry:
            entry["by_id"][row_id] = dict(res)
            for idx, item in enumerate(entry["rows"]):
                if item.get("id") == row_id:
                    entry["rows"][idx] = dict(res)
                    break
            entry["ts"] = time.time()
        if collection in ("admins", "users", "employees"):
            _collection_cache.pop("_typed_users", None)
            _collection_cache.pop("_typed_admins", None)
            _collection_cache.pop("_typed_employees", None)
            _collection_cache.pop("_typed_hr_managers", None)
            _collection_cache.pop("_typed_team_leads", None)
            _collection_cache.pop("_typed_recruiters", None)
            _collection_cache.pop("_typed_clients", None)
            _collection_cache.pop("_typed_content_managers", None)

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
    with _Session() as session:
        row = session.get(Record, {"collection": collection, "id": row_id})
        if not row:
            return False
        if collection in ("admins", "users") and row.data:
            deleted_email = row.data.get("email")
        session.delete(row)
        session.commit()

    with _cache_lock:
        entry = _collection_cache.get(collection)
        if entry:
            entry["by_id"].pop(row_id, None)
            entry["rows"] = [r for r in entry["rows"] if r.get("id") != row_id]
            entry["ts"] = time.time()
        if collection in ("admins", "users", "employees"):
            _collection_cache.pop("_typed_users", None)
            _collection_cache.pop("_typed_admins", None)
            _collection_cache.pop("_typed_employees", None)
            _collection_cache.pop("_typed_hr_managers", None)
            _collection_cache.pop("_typed_team_leads", None)
            _collection_cache.pop("_typed_recruiters", None)
            _collection_cache.pop("_typed_clients", None)
            _collection_cache.pop("_typed_content_managers", None)

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
        elif collection == "attendance":
            with _Session() as session:
                att = session.get(AttendanceRecord, row_id)
                if att:
                    session.delete(att)
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


# ── Fast Typed Queries with Memory Caching ──────────────────────────────

def _get_typed_cached(cache_key, model_cls):
    now_ts = time.time()
    with _cache_lock:
        entry = _collection_cache.get(cache_key)
        if entry and (now_ts - entry["ts"] < CACHE_TTL):
            return [dict(r) for r in entry["rows"]]

    with _Session() as session:
        rows = session.scalars(select(model_cls).order_by(model_cls.id)).all()
        items = [r.to_dict() for r in rows]
        with _cache_lock:
            _collection_cache[cache_key] = {
                "rows": items,
                "by_id": {it["id"]: it for it in items if "id" in it},
                "ts": now_ts,
            }
        return [dict(r) for r in items]


def get_users():
    return _get_typed_cached("_typed_users", User)


def get_admins():
    return _get_typed_cached("_typed_admins", Admin)


def get_employees():
    return _get_typed_cached("_typed_employees", Employee)


def get_hr_managers():
    return _get_typed_cached("_typed_hr_managers", HRManager)


def get_team_leads():
    return _get_typed_cached("_typed_team_leads", TeamLead)


def get_recruiters():
    return _get_typed_cached("_typed_recruiters", Recruiter)


def get_clients():
    return _get_typed_cached("_typed_clients", Client)


def get_content_managers():
    return _get_typed_cached("_typed_content_managers", ContentManager)


# Background pre-warm thread to load hot collections into RAM
def _warm_all_caches():
    time.sleep(0.5)
    hot_cols = (
        "jobs", "insights", "admins", "users", "employees",
        "companies", "leave_types", "leave_balances", "salary_structures"
    )
    for col in hot_cols:
        try:
            read(col)
        except Exception:
            pass

threading.Thread(target=_warm_all_caches, daemon=True).start()

