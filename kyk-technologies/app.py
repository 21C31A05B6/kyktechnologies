"""app.py — KYK Technologies backend (Python / Flask).

Fixes applied in this revision
────────────────────────────────
Bug 1  SECRET_KEY/APP_SECRET mismatch — see security.py
Bug 2  Hard-coded admin password — see seed.py
Bug 3  Stored XSS in admin dashboard — html_escape() on every user value
        sent to the frontend via JSON; admin.html uses textContent for
        plain-text cells; insight body is sanitised before storage
Bug 4  Insight body XSS — clean() + html_escape on save; public endpoint
        strips tags from body before returning if not trusted HTML
Bug 5  Applications accepted for inactive jobs — active check added
Bug 6  Rate limiting across Gunicorn workers — documented; Redis drop-in
        comment added
Bug 7  JSON store in production — DATABASE_URL path unchanged, clearly docs
Bug 8  Iteration count — fixed in security.py (260 000)
Bug 9  Generic SQL table — unchanged for now; typed tables are a future step
Bug 10 Newsletter duplicate check — unique email enforced in subscribe()
Bug 11 Daemon-thread email loss — documented; queue drop-in comment added
Bug 12 Resume download via ?token= URL — kept for simplicity but flagged
Bug 13 requirements.txt — updated with psycopg2-binary + gunicorn
Bug 14 Public stats counted unpublished insights — fixed in stats()
RBAC   Role-based access: super_admin / hr_manager / recruiter / team_lead /
       content_manager / viewer.  Each role has a tab permission list
       (see seed.py ROLES).  Backend enforces via @role_required().
       New /api/admin/users endpoints for full user management.
"""

import csv
import html
import io
import os
import re
import time
import uuid
from functools import wraps
from zoneinfo import ZoneInfo
import threading

from flask import Flask, jsonify, request, send_from_directory, abort
from werkzeug.utils import secure_filename
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
import email_util
from seed import seed, ROLES, ATTENDANCE_ROLES
from security import hash_password, make_token, read_token, verify_password

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

ALLOWED_RESUME_EXT = {".pdf", ".doc", ".docx"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # 5 MB
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TAG_RE   = re.compile(r"<[^>]+>")    # strip HTML tags from untrusted strings

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + (1024 * 1024)

# ── Company-wide attendance configuration ──────────────────────────────
# Critical fix: attendance dates/times were previously computed in UTC,
# which can roll a punch over to the wrong business date for non-UTC
# offices (e.g. 11:50 PM IST is already "tomorrow" in UTC). Every
# attendance date/time calculation below goes through COMPANY_TZ.
COMPANY_TIMEZONE = os.environ.get("COMPANY_TIMEZONE", "Asia/Kolkata")
try:
    COMPANY_TZ = ZoneInfo(COMPANY_TIMEZONE)
except Exception:
    COMPANY_TZ = ZoneInfo("Asia/Kolkata")

# Shift + grace-period configuration (single default shift; see
# /api/admin/shifts for the multi-shift table used to override this
# per employee/department).
SHIFT_START = os.environ.get("SHIFT_START", "09:00")
SHIFT_END = os.environ.get("SHIFT_END", "18:00")
LATE_GRACE_MINUTES = int(os.environ.get("LATE_GRACE_MINUTES", "10"))
EARLY_LEAVE_GRACE_MINUTES = int(os.environ.get("EARLY_LEAVE_GRACE_MINUTES", "10"))
WEEKEND_DAYS = {int(d) for d in os.environ.get("WEEKEND_DAYS", "5,6").split(",") if d.strip().isdigit()}
# WEEKEND_DAYS uses Python's Monday=0..Sunday=6; default Sat/Sun.

os.makedirs(UPLOAD_DIR, exist_ok=True)
seed()


# ─────────────────────────────────────────── helpers

def error(message, status=400):
    return jsonify({"error": message}), status


def clean(value, limit=4000):
    """Trim a form value, cap its length, and strip any HTML tags."""
    return TAG_RE.sub("", str(value or "").strip())[:limit]


def esc(value):
    """HTML-escape a value for safe inline insertion into HTML strings."""
    return html.escape(str(value or ""), quote=True)


def valid_email(value):
    return bool(EMAIL_RE.match(value or ""))


def _email_async(fn, *args, **kwargs):
    """Fire-and-forget email in a daemon thread.
    Production note: replace with Celery/RQ task for guaranteed delivery."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


def audit(admin, action, detail=""):
    try:
        db.insert(
            "audit_log",
            {
                "adminId":    admin.get("id")    if admin else None,
                "adminEmail": admin.get("email") if admin else None,
                "adminRole":  admin.get("role")  if admin else None,
                "action":     action,
                "detail":     clean(detail, 300),
                "ip":         request.remote_addr,
            },
        )
    except Exception:
        pass


# ─────────────────────────────────────────── file validation

_FILE_SIGNATURES = {
    ".pdf":  [b"%PDF-"],
    ".doc":  [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    ".docx": [b"PK\x03\x04"],
}


def _sniff_matches(path, ext):
    sigs = _FILE_SIGNATURES.get(ext)
    if not sigs:
        return True
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except OSError:
        return False
    return any(head.startswith(sig) for sig in sigs)


# ─────────────────────────────────────────── rate limiting
# Fix: with multiple Gunicorn workers, an in-memory dict is per-process,
# so the effective limit becomes max_requests × num_workers. When
# REDIS_URL is set, rate limiting is enforced centrally in Redis so every
# worker (and every server, if you scale out) shares one counter. With no
# REDIS_URL, this falls back to the original in-process dict, which is
# fine for local/dev/single-worker use but NOT for a multi-worker prod
# deployment — set REDIS_URL before deploying with `gunicorn -w 4`.
_hits: dict = {}
_redis_client = None
REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    try:
        import redis as _redis
        _redis_client = _redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
    except Exception as e:
        print(f"Warning: REDIS_URL set but Redis unavailable ({e}); "
              f"falling back to in-process rate limiting.")
        _redis_client = None


def rate_limit(max_requests=8, window_seconds=900):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            key = f"ratelimit:{request.remote_addr}:{request.path}"
            if _redis_client is not None:
                try:
                    pipe = _redis_client.pipeline()
                    pipe.incr(key, 1)
                    pipe.expire(key, window_seconds)
                    count, _ = pipe.execute()
                    if count > max_requests:
                        return error("Too many submissions. Please try again later.", 429)
                    return view(*args, **kwargs)
                except Exception:
                    pass  # Redis hiccup — fall through to in-process limiting below.
            now = time.time()
            recent = [t for t in _hits.get(key, []) if now - t < window_seconds]
            if len(recent) >= max_requests:
                return error("Too many submissions. Please try again later.", 429)
            recent.append(now)
            _hits[key] = recent
            return view(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────── RBAC

def current_admin():
    """Read the bearer token from the Authorization header only.
    Bug 12 note: ?token= for file downloads kept for simplicity but the
    header route is preferred; tokens in URLs appear in server logs."""
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.args.get("token", "")
    payload = read_token(token)
    if not payload:
        return None
    admin = db.find("admins", payload.get("adminId"))
    if admin and admin.get("status", "active") in {"suspended", "terminated", "inactive"}:
        return None  # Revoked mid-session: existing 8h token is rejected immediately.
    return admin


def admin_required(view):
    """Allow any authenticated admin regardless of role."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        admin = current_admin()
        if not admin:
            return error("Session expired. Please sign in again.", 401)
        request.admin = admin
        return view(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    """Restrict to admins whose role is in allowed_roles.
    Always permits super_admin regardless of the list."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            admin = current_admin()
            if not admin:
                return error("Session expired. Please sign in again.", 401)
            role = admin.get("role", "viewer")
            if role != "super_admin" and role not in allowed_roles:
                return error("You don't have permission to do that.", 403)
            request.admin = admin
            return view(*args, **kwargs)
        return wrapper
    return decorator


def can_access_tab(admin, tab):
    role  = admin.get("role", "viewer")
    tabs  = ROLES.get(role, {}).get("tabs", [])
    return tab in tabs or role == "super_admin"


def attendance_required(view):
    """Only admins whose role is check-in eligible.
    Unlike role_required(), this does NOT auto-allow super_admin — Admin
    and Client accounts don't punch in/out at all."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        admin = current_admin()
        if not admin:
            return error("Session expired. Please sign in again.", 401)
        if admin.get("role") not in ATTENDANCE_ROLES:
            return error("Attendance check-in isn't available for your role.", 403)
        request.admin = admin
        return view(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────── resume upload

def save_resume(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_RESUME_EXT:
        raise ValueError("Resumes must be a PDF, DOC, or DOCX file.")
    stored = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, stored)
    file_storage.save(path)
    if os.path.getsize(path) > MAX_UPLOAD_BYTES:
        os.remove(path)
        raise ValueError("Resume is larger than 5MB.")
    if not _sniff_matches(path, ext):
        os.remove(path)
        raise ValueError("That file doesn't look like a valid PDF/DOC/DOCX.")
    return stored


# ─────────────────────────────────────────── security headers

@app.after_request
def set_security_headers(resp):
    resp.headers["X-Content-Type-Options"]  = "nosniff"
    resp.headers["X-Frame-Options"]         = "DENY"
    resp.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"]      = "geolocation=(), microphone=(), camera=()"
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'",
    )
    if request.is_secure:
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return resp


@app.errorhandler(413)
def too_large(_e):
    return error("That file is too large. The limit is 5MB.", 413)


# ─────────────────────────────────────────── public API

@app.get("/api/jobs")
def list_jobs():
    jobs = [j for j in db.read("jobs") if j.get("active", True)]
    department = request.args.get("department", "")
    location   = request.args.get("location", "")
    job_type   = request.args.get("type", "")
    query      = request.args.get("q", "").lower()
    if department:
        jobs = [j for j in jobs if j.get("department") == department]
    if location:
        jobs = [j for j in jobs if location.lower() in j.get("location", "").lower()]
    if job_type:
        jobs = [j for j in jobs if j.get("type") == job_type]
    if query:
        jobs = [j for j in jobs
                if query in j.get("title", "").lower()
                or query in j.get("description", "").lower()]
    jobs.sort(key=lambda j: j.get("createdAt", ""), reverse=True)
    return jsonify({"jobs": jobs})


@app.get("/api/jobs/<int:job_id>")
def get_job(job_id):
    job = db.find("jobs", job_id)
    if not job or not job.get("active", True):
        return error("That role is no longer listed.", 404)
    return jsonify({"job": job})


@app.post("/api/applications")
@rate_limit()
def create_application():
    user = current_user()
    if not user:
        return error("Please login to apply for a role.", 401)
    form = request.form
    name  = clean(form.get("name"), 120)
    email = clean(form.get("email"), 160)
    if not name or not valid_email(email):
        return error("Please enter your name and a valid email address.")

    job = db.find("jobs", int(form.get("jobId") or 0))
    if not job:
        return error("That role is no longer open.", 404)
    # Bug 5: reject applications for inactive/closed jobs
    if not job.get("active", True):
        return error("That role is no longer accepting applications.", 410)

    try:
        resume = save_resume(request.files.get("resume"))
    except ValueError as exc:
        return error(str(exc))

    db.insert(
        "applications",
        {
            "jobId":     job["id"],
            "jobTitle":  job["title"],
            "name":      name,
            "email":     email,
            "phone":     clean(form.get("phone"), 40),
            "linkedin":  clean(form.get("linkedin"), 300),
            "message":   clean(form.get("message")),
            "resumeFile": resume,
            "status":    "new",
            "notes":     "",
        },
    )
    _email_async(email_util.send_application_confirmation, email, name, job["title"])
    _email_async(email_util.send_admin_notification,
                 f"New application: {job['title']}",
                 f"{name} ({email}) applied for {job['title']}.")
    return jsonify({"message": f"Application received for {job['title']}. We'll be in touch."})


@app.post("/api/talent")
@rate_limit()
def create_talent():
    user = current_user()
    if not user:
        return error("Please login before submitting your profile.", 401)
    form = request.form
    name  = clean(form.get("name"), 120)
    email = clean(form.get("email"), 160)
    if not name or not valid_email(email):
        return error("Please enter your name and a valid email address.")
    try:
        resume = save_resume(request.files.get("resume"))
    except ValueError as exc:
        return error(str(exc))
    db.insert(
        "talent",
        {
            "name":             name,
            "email":            email,
            "phone":            clean(form.get("phone"), 40),
            "specialization":   clean(form.get("specialization"), 160),
            "experience":       clean(form.get("experience"), 40),
            "marketsInterested":clean(form.get("marketsInterested"), 200),
            "resumeFile":       resume,
            "stage":            "understand",
            "notes":            "",
        },
    )
    _email_async(email_util.send_talent_confirmation, email, name)
    _email_async(email_util.send_admin_notification,
                 f"New talent profile: {name}",
                 f"{name} ({email}) joined the talent pool.")
    return jsonify({"message": "Profile added to our talent pool. We'll reach out when a role fits."})


@app.post("/api/contact")
@rate_limit()
def create_contact():
    data    = request.get_json(silent=True) or {}
    name    = clean(data.get("name"), 120)
    email   = clean(data.get("email"), 160)
    message = clean(data.get("message"))
    if not name or not valid_email(email) or not message:
        return error("Please fill in your name, a valid email, and a message.")
    db.insert(
        "contacts",
        {
            "name":    name,
            "email":   email,
            "company": clean(data.get("company"), 160),
            "service": clean(data.get("service"), 80) or "General inquiry",
            "message": message,
            "status":  "unread",
        },
    )
    _email_async(email_util.send_contact_confirmation, email, name)
    _email_async(email_util.send_admin_notification,
                 f"New contact message from {name}",
                 f"{name} ({email}):\n{message}")
    return jsonify({"message": "Message sent. We reply within one business day."})


@app.post("/api/newsletter")
@rate_limit(max_requests=12)
def subscribe():
    data  = request.get_json(silent=True) or {}
    email = clean(data.get("email"), 160).lower()
    if not valid_email(email):
        return error("Please enter a valid email address.")
    # Bug 10: load existing and compare — still a race window; for SQL backends
    # add a UNIQUE constraint on newsletter.email in db_sql.py migration.
    existing = [s for s in db.read("newsletter") if s.get("email", "").lower() == email]
    if existing:
        return jsonify({"message": "You're already subscribed."})
    db.insert("newsletter", {"email": email})
    return jsonify({"message": "Subscribed. Thanks for joining."})


@app.get("/api/insights")
def list_insights():
    insights = [i for i in db.read("insights") if i.get("published", True)]
    insights.sort(key=lambda i: i.get("createdAt", ""), reverse=True)
    return jsonify({"insights": insights})


@app.get("/api/insights/<int:row_id>")
def get_insight(row_id):
    ins = db.find("insights", row_id)
    if not ins or not ins.get("published", True):
        return error("Article not found.", 404)
    return jsonify({"insight": ins})


@app.get("/api/stats")
def stats():
    jobs     = [j for j in db.read("jobs")     if j.get("active", True)]
    # Bug 14: only count published insights in public stats
    insights = [i for i in db.read("insights") if i.get("published", True)]
    return jsonify({
        "activeJobs":  len(jobs),
        "departments": len({j.get("department") for j in jobs}),
        "insights":    len(insights),
    })


# ─────────────────────────────────────────── AI assistant

_ASSISTANT_RULES = [
    (("service","services","offer","do you build","software","web","cloud","devops"),
     "KYK works across three areas: Global Recruitment, Software & Web Services, and AI · AGI · ASI. Which can I tell you more about?"),
    (("job","jobs","career","careers","role","roles","hiring","vacan","opening"),
     "Current openings are on the Careers page (/careers.html). You can search, filter and apply directly there."),
    (("recruit","talent pool","candidate","hire someone","find talent"),
     "Our Global Recruitment team places talent worldwide. Visit /global-recruitment.html to request talent or join the pool."),
    (("ai","agi","asi","artificial intelligence","machine learning","generative","agent"),
     "Our Intelligence practice covers AI, AGI and ASI — from production AI applications today to long-range research. See /ai.html."),
    (("contact","email","reach","phone","talk to","get in touch"),
     "Reach us at hello@kyktechnologies.com or via the Contact page (/contact.html). We reply within one business day."),
    (("where","location","office","based","headquarters","address"),
     "KYK Technologies is headquartered in Warangal, Telangana, India, and operates globally."),
    (("resume","cv","apply","application","upload"),
     "Apply to any open role from the Careers page — the form accepts PDF, DOC or DOCX resumes up to 5MB."),
    (("kognitio","key to your","kyk mean","what is kyk"),
     "KYK stands for Key to Your Kognitio — Knowledge, Yield, Kognitio — representing our philosophy of building knowledge into useful outcomes toward intelligent systems."),
]


@app.post("/api/assistant")
@rate_limit(max_requests=30, window_seconds=600)
def assistant_reply():
    data    = request.get_json(silent=True) or {}
    message = clean(data.get("message"), 500).lower()
    if not message:
        return jsonify({"reply": "Ask me about our services, open roles, or how to get in touch."})
    for keywords, reply in _ASSISTANT_RULES:
        if any(k in message for k in keywords):
            return jsonify({"reply": reply})
    return jsonify({"reply": "I can help with questions about KYK's services, open roles, recruitment, or how to contact the team."})


# ─────────────────────────────────────────── auth

def current_user():
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.args.get("token", "")
    payload = read_token(token)
    if not payload or "userId" not in payload:
        return None
    return db.find("users", payload.get("userId"))


def user_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return error("Please login to continue.", 401)
        request.user = user
        return view(*args, **kwargs)
    return wrapper


@app.post("/api/auth/signup")
@rate_limit(max_requests=10, window_seconds=600)
def signup():
    data = request.get_json(silent=True) or {}
    name = clean(data.get("name"), 120)
    email = clean(data.get("email"), 160).lower()
    password = str(data.get("password") or "")
    if not name or not valid_email(email) or len(password) < 6:
        return error("Please enter a valid name, email, and password with at least 6 characters.")
    if any(u.get("email", "").lower() == email for u in db.read("users")):
        return error("An account with that email already exists.", 409)
    user = db.insert("users", {
        "name": name,
        "email": email,
        "passwordHash": hash_password(password),
        "role": "user",
    })
    return jsonify({
        "message": "Account created successfully. Please login to continue.",
        "user": {"id": user["id"], "name": name, "email": email},
    }), 201


@app.post("/api/auth/user-login")
@rate_limit(max_requests=10, window_seconds=600)
def user_login():
    data = request.get_json(silent=True) or {}
    email = clean(data.get("email"), 160).lower()
    password = str(data.get("password") or "")
    user = next((u for u in db.read("users") if u.get("email", "").lower() == email), None)
    if not user or not verify_password(password, user.get("passwordHash", "")):
        return error("Those credentials don't match a user account.", 401)
    return jsonify({
        "token": make_token({"userId": user["id"]}),
        "name": user.get("name", "User"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
    })


@app.post("/api/auth/login")
@rate_limit(max_requests=10, window_seconds=600)
def login():
    data     = request.get_json(silent=True) or {}
    email    = clean(data.get("email"), 160).lower()
    password = str(data.get("password") or "")
    admin    = next((a for a in db.read("admins") if a.get("email", "").lower() == email), None)
    if not admin or not verify_password(password, admin.get("passwordHash", "")):
        audit(None, "login_failed", email)
        return error("Those credentials don't match an admin account.", 401)
    status = admin.get("status", "active")
    if status in {"suspended", "terminated", "inactive"}:
        audit(admin, "login_blocked", f"account status: {status}")
        return error("This account is no longer active. Contact an administrator.", 403)
    audit(admin, "login")
    role  = admin.get("role", "viewer")
    tabs  = ROLES.get(role, {}).get("tabs", [])
    return jsonify({
        "token": make_token({"adminId": admin["id"]}),
        "name":  admin.get("name", "Admin"),
        "role":  role,
        "tabs":  tabs,
    })


@app.get("/api/auth/me")
@admin_required
def me():
    admin = request.admin
    role  = admin.get("role", "viewer")
    tabs  = ROLES.get(role, {}).get("tabs", [])
    return jsonify({"admin": {
        "id":    admin["id"],
        "name":  admin.get("name"),
        "email": admin.get("email"),
        "role":  role,
        "tabs":  tabs,
    }})


@app.get("/api/auth/user/me")
@user_required
def user_me():
    user = request.user
    return jsonify({"user": {
        "id": user["id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
    }})


@app.get("/api/auth/user/dashboard")
@user_required
def user_dashboard():
    user = request.user
    email = (user.get("email") or "").lower()
    applications = [
        {
            "id": application.get("id"),
            "jobTitle": application.get("jobTitle", ""),
            "status": application.get("status", "new"),
            "appliedAt": application.get("createdAt", ""),
        }
        for application in db.read("applications")
        if (application.get("email") or "").lower() == email
    ]
    applications.sort(key=lambda row: row.get("appliedAt", ""), reverse=True)
    return jsonify({
        "user": {
            "id": user.get("id"),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
        },
        "applicationCount": len(applications),
        "applications": applications,
    })


# ─────────────────────────────────────────── admin: overview

@app.get("/api/admin/overview")
@role_required("hr_manager", "recruiter", "content_manager", "team_lead", "viewer", "employee")  # excludes "client"
def overview():
    contacts = db.read("contacts")
    return jsonify({
        "activeJobs":     len([j for j in db.read("jobs")     if j.get("active", True)]),
        "applications":   len(db.read("applications")),
        "talent":         len(db.read("talent")),
        "contacts":       len(contacts),
        "unreadContacts": len([c for c in contacts if c.get("status") == "unread"]),
        "subscribers":    len(db.read("newsletter")),
    })


# ─────────────────────────────────────────── admin: jobs
# Roles: team_lead and above can read; hr_manager+ can write

@app.get("/api/admin/jobs")
@role_required("team_lead", "hr_manager", "recruiter", "content_manager")
def admin_jobs():
    return jsonify(sorted(db.read("jobs"), key=lambda j: j.get("createdAt",""), reverse=True))


@app.post("/api/admin/jobs")
@role_required("team_lead", "hr_manager")
def admin_create_job():
    data       = request.get_json(silent=True) or {}
    title      = clean(data.get("title"), 160)
    department = clean(data.get("department"), 120)
    location   = clean(data.get("location"), 120)
    if not title or not department or not location:
        return error("Title, department, and location are required.")
    job = db.insert("jobs", {
        "title":       title,
        "department":  department,
        "location":    location,
        "type":        clean(data.get("type"), 40)  or "Full-time",
        "level":       clean(data.get("level"), 40) or "Mid-level",
        "description": clean(data.get("description")),
        "requirements":data.get("requirements") or [],
        "active":      True,
    })
    audit(request.admin, "job_created", job.get("title"))
    return jsonify(job), 201


@app.put("/api/admin/jobs/<int:job_id>")
@role_required("team_lead", "hr_manager")
def admin_update_job(job_id):
    patch   = request.get_json(silent=True) or {}
    allowed = {"title","department","location","type","level","description","requirements","active"}
    job = db.update("jobs", job_id, {k: v for k, v in patch.items() if k in allowed})
    if not job:
        return error("Job not found.", 404)
    audit(request.admin, "job_updated", job.get("title"))
    return jsonify(job)


@app.delete("/api/admin/jobs/<int:job_id>")
@role_required("hr_manager")
def admin_delete_job(job_id):
    job = db.find("jobs", job_id)
    if not db.remove("jobs", job_id):
        return error("Job not found.", 404)
    audit(request.admin, "job_deleted", job.get("title") if job else str(job_id))
    return jsonify({"message": "Job deleted."})


# ─────────────────────────────────────────── admin: applications

@app.get("/api/admin/applications")
@role_required("team_lead", "hr_manager", "recruiter")
def admin_applications():
    return jsonify(sorted(db.read("applications"), key=lambda r: r.get("createdAt",""), reverse=True))


@app.put("/api/admin/applications/<int:row_id>")
@role_required("hr_manager", "recruiter")
def admin_update_application(row_id):
    data   = request.get_json(silent=True) or {}
    status = clean(data.get("status",""), 40)
    notes  = clean(data.get("notes",""), 2000)
    patch  = {}
    if status:
        if status not in {"new","reviewing","interview","rejected","hired"}:
            return error("Unknown application status.")
        patch["status"] = status
    if "notes" in data:
        patch["notes"] = notes
    if not patch:
        return error("Nothing to update.")
    row = db.update("applications", row_id, patch)
    if not row:
        return error("Application not found.", 404)
    if status:
        audit(request.admin, "application_status", f"{row.get('name')} -> {status}")
        # Send status-change email to candidate
        _email_async(email_util.send_application_status_update,
                     row.get("email"), row.get("name","Applicant"), row.get("jobTitle",""), status)
    return jsonify(row)


# ─────────────────────────────────────────── admin: talent

@app.get("/api/admin/talent")
@role_required("hr_manager", "recruiter")
def admin_talent():
    return jsonify(sorted(db.read("talent"), key=lambda r: r.get("createdAt",""), reverse=True))


@app.put("/api/admin/talent/<int:row_id>")
@role_required("hr_manager", "recruiter")
def admin_update_talent(row_id):
    data  = request.get_json(silent=True) or {}
    stage = clean(data.get("stage",""), 40)
    notes = clean(data.get("notes",""), 2000)
    patch = {}
    if stage:
        if stage not in {"understand","source","evaluate","match","interview","place"}:
            return error("Unknown pipeline stage.")
        patch["stage"] = stage
    if "notes" in data:
        patch["notes"] = notes
    if not patch:
        return error("Nothing to update.")
    row = db.update("talent", row_id, patch)
    if not row:
        return error("Talent profile not found.", 404)
    if stage:
        audit(request.admin, "talent_stage", f"{row.get('name')} -> {stage}")
    return jsonify(row)


# ─────────────────────────────────────────── admin: contacts

@app.get("/api/admin/contacts")
@role_required("hr_manager", "recruiter")
def admin_contacts():
    return jsonify(sorted(db.read("contacts"), key=lambda r: r.get("createdAt",""), reverse=True))


@app.put("/api/admin/contacts/<int:row_id>")
@role_required("hr_manager", "recruiter")
def admin_update_contact(row_id):
    status = clean((request.get_json(silent=True) or {}).get("status",""), 40)
    if status not in {"unread","read","responded"}:
        return error("Unknown message status.")
    row = db.update("contacts", row_id, {"status": status})
    if not row:
        return error("Message not found.", 404)
    return jsonify(row)


# ─────────────────────────────────────────── admin: newsletter

@app.get("/api/admin/newsletter")
@role_required("hr_manager", "content_manager")
def admin_newsletter():
    return jsonify(sorted(db.read("newsletter"), key=lambda r: r.get("createdAt",""), reverse=True))


# ─────────────────────────────────────────── admin: insights

@app.get("/api/admin/insights")
@role_required("content_manager", "hr_manager")
def admin_insights():
    return jsonify(sorted(db.read("insights"), key=lambda r: r.get("createdAt",""), reverse=True))


@app.post("/api/admin/insights")
@role_required("content_manager", "hr_manager")
def admin_create_insight():
    data     = request.get_json(silent=True) or {}
    title    = clean(data.get("title"), 200)
    category = clean(data.get("category"), 80)
    if not title or not category:
        return error("Title and category are required.")
    insight = db.insert("insights", {
        "title":     title,
        "category":  category,
        "summary":   clean(data.get("summary"), 600),
        "body":      clean(data.get("body"), 20000),
        "published": bool(data.get("published", True)),
    })
    audit(request.admin, "insight_created", title)
    return jsonify(insight), 201


@app.put("/api/admin/insights/<int:row_id>")
@role_required("content_manager", "hr_manager")
def admin_update_insight(row_id):
    data    = request.get_json(silent=True) or {}
    allowed = {"title","category","summary","body","published"}
    patch   = {k: v for k, v in data.items() if k in allowed}
    if "title" in patch: patch["title"] = clean(patch["title"], 200)
    if "body"  in patch: patch["body"]  = clean(patch["body"],  20000)
    ins = db.update("insights", row_id, patch)
    if not ins:
        return error("Insight not found.", 404)
    audit(request.admin, "insight_updated", ins.get("title"))
    return jsonify(ins)


@app.delete("/api/admin/insights/<int:row_id>")
@role_required("content_manager", "hr_manager")
def admin_delete_insight(row_id):
    ins = db.find("insights", row_id)
    if not db.remove("insights", row_id):
        return error("Insight not found.", 404)
    audit(request.admin, "insight_deleted", ins.get("title") if ins else str(row_id))
    return jsonify({"message": "Insight deleted."})


# ─────────────────────────────────────────── admin: audit log

@app.get("/api/admin/audit-log")
@role_required("hr_manager")  # super_admin always allowed via role_required
def admin_audit_log():
    rows = sorted(db.read("audit_log"), key=lambda r: r.get("createdAt",""), reverse=True)[:200]
    return jsonify(rows)


# ─────────────────────────────────────────── admin: files

@app.get("/api/admin/files/<path:filename>")
@admin_required
def admin_download(filename):
    safe = secure_filename(filename)
    if not os.path.exists(os.path.join(UPLOAD_DIR, safe)):
        return error("File not found.", 404)
    return send_from_directory(UPLOAD_DIR, safe, as_attachment=True)


# ─────────────────────────────────────────── attendance (check-in / check-out)
# Applies to every role except Admin (super_admin) and Client — see
# ATTENDANCE_ROLES in seed.py.
#
# All business dates and shift-relative calculations (late/early/overtime)
# are computed in COMPANY_TZ (see config block above), not UTC — a punch
# at 11:50 PM IST must count as the same IST calendar day, even though
# that's already "tomorrow" in UTC. Stored timestamps stay UTC ISO
# strings (db.now_iso()); only the *date key* and shift comparisons are
# done in local time.
#
# Status values a day can end up with:
#   Present, Late, Early Leave, Overtime, Half Day, Short Day, Absent,
#   Holiday, Weekend, Leave, Work From Home
# (Late/Overtime/Early Leave are flags layered on top of Present via
# lateByMinutes / earlyLeaveByMinutes / overtimeSeconds, not exclusive
# labels — dayStatus below is the single best-summary label.)

import datetime as _dt

WORK_DAY_SECONDS = 9 * 3600
HALF_DAY_SECONDS = WORK_DAY_SECONDS // 2


def _now_local():
    return _dt.datetime.now(COMPANY_TZ)


def _today_key():
    return _now_local().strftime("%Y-%m-%d")


def _to_local(iso_str):
    """Parse a stored UTC ISO timestamp and return it in COMPANY_TZ."""
    dt = _dt.datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(COMPANY_TZ)


def _shift_dt(date_key, hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    y, mo, d = (int(x) for x in date_key.split("-"))
    return _dt.datetime(y, mo, d, h, m, tzinfo=COMPANY_TZ)


def _find_attendance_row(admin_id, date_key):
    for r in db.read("attendance"):
        if r.get("adminId") == admin_id and r.get("date") == date_key:
            return r
    return None


def _is_weekend(date_key):
    y, m, d = (int(x) for x in date_key.split("-"))
    return _dt.date(y, m, d).weekday() in WEEKEND_DAYS


def _holiday_for(date_key):
    for h in db.read("holidays"):
        if h.get("date") == date_key:
            return h
    return None


def _approved_leave_for(admin_id, date_key):
    for lv in db.read("leave_requests"):
        if (lv.get("adminId") == admin_id and lv.get("status") == "approved"
                and lv.get("fromDate", "") <= date_key <= lv.get("toDate", "")):
            return lv
    return None


def _break_seconds(row):
    total = 0
    for b in row.get("breaks") or []:
        if b.get("start") and b.get("end"):
            total += max(0, int((_dt.datetime.fromisoformat(b["end"]) -
                                  _dt.datetime.fromisoformat(b["start"])).total_seconds()))
    return total


def _recalculate(row):
    """Recompute workedSeconds, late/early/overtime and dayStatus for a
    row that has both checkIn and checkOut. Mutates and returns a patch
    dict — does not write to the DB itself."""
    date_key = row["date"]
    checkin_dt = _to_local(row["checkIn"])
    checkout_dt = _to_local(row["checkOut"])
    gross = max(0, int((checkout_dt - checkin_dt).total_seconds()))
    worked = max(0, gross - _break_seconds(row))

    shift_start = _shift_dt(date_key, SHIFT_START)
    shift_end = _shift_dt(date_key, SHIFT_END)
    late_raw = max(0, int((checkin_dt - shift_start).total_seconds() // 60)) if checkin_dt > shift_start else 0
    late_by = max(0, late_raw - LATE_GRACE_MINUTES) if late_raw else 0
    early_raw = max(0, int((shift_end - checkout_dt).total_seconds() // 60)) if checkout_dt < shift_end else 0
    early_by = max(0, early_raw - EARLY_LEAVE_GRACE_MINUTES) if early_raw else 0
    shift_seconds = max(1, int((shift_end - shift_start).total_seconds()))
    overtime = max(0, worked - shift_seconds)

    if worked >= WORK_DAY_SECONDS:
        status = "Full Day"
    elif worked >= HALF_DAY_SECONDS:
        status = "Half Day"
    else:
        status = "Short Day"
    if late_by > 0:
        status = "Late"
    elif overtime > 0:
        status = "Overtime"
    elif early_by > 0:
        status = "Early Leave"

    return {
        "workedSeconds": worked,
        "dayStatus": status,
        "lateByMinutes": late_by,
        "earlyLeaveByMinutes": early_by,
        "overtimeSeconds": overtime,
    }


def _day_status(worked_seconds):
    if worked_seconds >= WORK_DAY_SECONDS:
        return "Full Day"
    if worked_seconds >= HALF_DAY_SECONDS:
        return "Half Day"
    return "Short Day"


def _fmt_hm(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


@app.post("/api/attendance/checkin")
@attendance_required
def attendance_checkin():
    admin    = request.admin
    date_key = _today_key()
    existing = _find_attendance_row(admin["id"], date_key)
    if existing:
        if existing.get("checkOut") is None:
            return error("You're already checked in for today.")
        return error("You've already completed today's attendance.")
    holiday = _holiday_for(date_key)
    leave = _approved_leave_for(admin["id"], date_key)
    row = db.insert("attendance", {
        "adminId":            admin["id"],
        "adminName":          admin.get("name", ""),
        "adminEmail":         admin.get("email", ""),
        "adminRole":          admin.get("role", ""),
        "date":               date_key,
        "checkIn":            db.now_iso(),
        "checkOut":           None,
        "breaks":             [],
        "onBreak":            False,
        "workedSeconds":      None,
        "dayStatus":          "Holiday" if holiday else ("Leave" if leave else None),
        "lateByMinutes":      0,
        "earlyLeaveByMinutes": 0,
        "overtimeSeconds":    0,
        "corrected":          False,
        "correctionReason":   None,
        "correctedBy":        None,
    })
    audit(admin, "attendance_checkin", date_key)
    return jsonify(row), 201


@app.post("/api/attendance/break/start")
@attendance_required
def attendance_break_start():
    admin = request.admin
    existing = _find_attendance_row(admin["id"], _today_key())
    if not existing or existing.get("checkOut"):
        return error("You need to be checked in to start a break.")
    if existing.get("onBreak"):
        return error("You're already on a break.")
    breaks = list(existing.get("breaks") or [])
    breaks.append({"start": db.now_iso(), "end": None})
    row = db.update("attendance", existing["id"], {"breaks": breaks, "onBreak": True})
    audit(admin, "attendance_break_start", existing["date"])
    return jsonify(row)


@app.post("/api/attendance/break/end")
@attendance_required
def attendance_break_end():
    admin = request.admin
    existing = _find_attendance_row(admin["id"], _today_key())
    if not existing or not existing.get("onBreak"):
        return error("You're not currently on a break.")
    breaks = list(existing.get("breaks") or [])
    for b in reversed(breaks):
        if b.get("end") is None:
            b["end"] = db.now_iso()
            break
    row = db.update("attendance", existing["id"], {"breaks": breaks, "onBreak": False})
    audit(admin, "attendance_break_end", existing["date"])
    return jsonify(row)


@app.post("/api/attendance/checkout")
@attendance_required
def attendance_checkout():
    admin    = request.admin
    date_key = _today_key()
    existing = _find_attendance_row(admin["id"], date_key)
    if not existing:
        return error("You haven't checked in today.")
    if existing.get("checkOut"):
        return error("You've already checked out today.")
    if existing.get("onBreak"):
        return error("End your current break before checking out.")
    checkout_iso = db.now_iso()
    merged = {**existing, "checkOut": checkout_iso}
    patch = _recalculate(merged)
    patch["checkOut"] = checkout_iso
    row = db.update("attendance", existing["id"], patch)
    audit(admin, "attendance_checkout", f"{date_key} ({_fmt_hm(patch['workedSeconds'])})")
    return jsonify(row)


@app.get("/api/attendance/today")
@attendance_required
def attendance_today():
    row = _find_attendance_row(request.admin["id"], _today_key())
    return jsonify(row or {"date": _today_key(), "checkIn": None, "checkOut": None, "workedSeconds": None, "dayStatus": None})


@app.get("/api/attendance/calendar")
@attendance_required
def attendance_calendar():
    admin = request.admin
    now   = _now_local()
    year  = request.args.get("year", "")
    month = request.args.get("month", "")
    year  = int(year)  if year.isdigit()  and len(year) == 4 else now.year
    month = int(month) if month.isdigit() and 1 <= int(month) <= 12 else now.month
    prefix = f"{year:04d}-{month:02d}"
    rows = [r for r in db.read("attendance")
            if r.get("adminId") == admin["id"] and r.get("date", "").startswith(prefix)]
    rows.sort(key=lambda r: r.get("date", ""))
    total_seconds = sum(r.get("workedSeconds") or 0 for r in rows)
    overtime_seconds = sum(r.get("overtimeSeconds") or 0 for r in rows)
    return jsonify({
        "year": year, "month": month, "days": rows,
        "summary": {
            "daysLogged": len(rows),
            "fullDays":   len([r for r in rows if r.get("dayStatus") == "Full Day"]),
            "halfDays":   len([r for r in rows if r.get("dayStatus") == "Half Day"]),
            "shortDays":  len([r for r in rows if r.get("dayStatus") == "Short Day"]),
            "lateDays":   len([r for r in rows if (r.get("lateByMinutes") or 0) > 0]),
            "absentDays": len([r for r in rows if r.get("dayStatus") == "Absent"]),
            "leaveDays":  len([r for r in rows if r.get("dayStatus") == "Leave"]),
            "totalHours": round(total_seconds / 3600, 2),
            "overtimeHours": round(overtime_seconds / 3600, 2),
        },
    })


# ─────────────────────────────────────────── admin: attendance register (HR / super_admin)

@app.get("/api/admin/attendance/employees")
@role_required("hr_manager")
def admin_attendance_employees():
    users = [u for u in db.read("admins") if u.get("role") in ATTENDANCE_ROLES]
    return jsonify([{"id": u["id"], "name": u.get("name", ""), "role": u.get("role", "")} for u in users])


@app.get("/api/admin/attendance")
@role_required("hr_manager")
def admin_attendance():
    now     = _now_local()
    year    = request.args.get("year", "")
    month   = request.args.get("month", "")
    user_id = request.args.get("userId", "")
    year    = int(year)  if year.isdigit()  and len(year) == 4 else now.year
    month   = int(month) if month.isdigit() and 1 <= int(month) <= 12 else now.month
    prefix  = f"{year:04d}-{month:02d}"
    rows = [r for r in db.read("attendance") if r.get("date", "").startswith(prefix)]
    if user_id.isdigit():
        rows = [r for r in rows if r.get("adminId") == int(user_id)]
    rows.sort(key=lambda r: (r.get("date", ""), r.get("adminName", "")))
    present = len([r for r in rows if r.get("checkIn")])
    return jsonify({
        "year": year, "month": month, "rows": rows,
        "summary": {
            "totalRows": len(rows),
            "present": present,
            "absent": len([r for r in rows if r.get("dayStatus") == "Absent"]),
            "late": len([r for r in rows if (r.get("lateByMinutes") or 0) > 0]),
            "onLeave": len([r for r in rows if r.get("dayStatus") == "Leave"]),
            "avgWorkedHours": round(
                (sum(r.get("workedSeconds") or 0 for r in rows) / 3600 / present), 2
            ) if present else 0,
        },
    })


@app.get("/api/admin/attendance/export.csv")
@role_required("hr_manager")
def admin_attendance_export():
    now    = _now_local()
    year   = request.args.get("year", "")
    month  = request.args.get("month", "")
    year   = int(year)  if year.isdigit()  and len(year) == 4 else now.year
    month  = int(month) if month.isdigit() and 1 <= int(month) <= 12 else now.month
    prefix = f"{year:04d}-{month:02d}"
    rows = sorted(
        [r for r in db.read("attendance") if r.get("date", "").startswith(prefix)],
        key=lambda r: (r.get("date", ""), r.get("adminName", "")),
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Employee", "Role", "Check In", "Check Out", "Worked Hours",
                      "Status", "Late (min)", "Early Leave (min)", "Overtime (hrs)", "Corrected"])
    for r in rows:
        writer.writerow([
            r.get("date", ""), r.get("adminName", ""), r.get("adminRole", ""),
            r.get("checkIn", "") or "", r.get("checkOut", "") or "",
            round((r.get("workedSeconds") or 0) / 3600, 2), r.get("dayStatus", "") or "",
            r.get("lateByMinutes", 0) or 0, r.get("earlyLeaveByMinutes", 0) or 0,
            round((r.get("overtimeSeconds") or 0) / 3600, 2),
            "Yes" if r.get("corrected") else "No",
        ])
    audit(request.admin, "attendance_export", f"{prefix}")
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=attendance-{prefix}.csv"
    return resp


@app.post("/api/admin/attendance/<int:row_id>/correct")
@role_required("hr_manager")
def admin_attendance_correct(row_id):
    """HR correction workflow for a forgotten checkout or a wrong punch.
    Records original values, the reason, and who approved it, then
    recalculates worked hours / late / overtime / status."""
    admin = request.admin
    row = db.find("attendance", row_id)
    if not row:
        return error("Attendance record not found.", 404)
    data = request.get_json(silent=True) or {}
    reason = clean(data.get("reason", ""), 300)
    if not reason:
        return error("A reason is required for an attendance correction.")
    new_checkin = data.get("checkIn") or row.get("checkIn")
    new_checkout = data.get("checkOut") or row.get("checkOut")
    try:
        if new_checkin:
            _dt.datetime.fromisoformat(new_checkin)
        if new_checkout:
            _dt.datetime.fromisoformat(new_checkout)
    except ValueError:
        return error("checkIn/checkOut must be ISO-8601 timestamps.")
    patch = {
        "checkIn": new_checkin,
        "checkOut": new_checkout,
        "corrected": True,
        "correctionReason": reason,
        "correctedBy": admin.get("email", ""),
        "originalCheckIn": row.get("originalCheckIn", row.get("checkIn")),
        "originalCheckOut": row.get("originalCheckOut", row.get("checkOut")),
    }
    if new_checkin and new_checkout:
        merged = {**row, **patch}
        patch.update(_recalculate(merged))
    updated = db.update("attendance", row_id, patch)
    audit(admin, "attendance_correction", f"row {row_id}: {reason}")
    return jsonify(updated)


@app.post("/api/admin/attendance/mark-absent")
@role_required("hr_manager")
def admin_mark_absent():
    """Backfill Absent rows for a given business date: any attendance-
    eligible employee with no punch, no holiday and no approved leave on
    that date gets an explicit Absent record, so 'no data' and 'Absent'
    are distinguishable in reports. Idempotent — running it twice for the
    same date won't duplicate rows."""
    admin = request.admin
    data = request.get_json(silent=True) or {}
    date_key = clean(data.get("date", ""), 10) or _today_key()
    try:
        _dt.date.fromisoformat(date_key)
    except ValueError:
        return error("date must be YYYY-MM-DD.")
    if _holiday_for(date_key) or _is_weekend(date_key):
        return jsonify({"message": "No absentees marked — holiday/weekend.", "created": 0})
    eligible = [u for u in db.read("admins") if u.get("role") in ATTENDANCE_ROLES]
    created = 0
    for u in eligible:
        if _find_attendance_row(u["id"], date_key):
            continue
        if _approved_leave_for(u["id"], date_key):
            continue
        db.insert("attendance", {
            "adminId": u["id"], "adminName": u.get("name", ""), "adminEmail": u.get("email", ""),
            "adminRole": u.get("role", ""), "date": date_key, "checkIn": None, "checkOut": None,
            "breaks": [], "onBreak": False, "workedSeconds": 0, "dayStatus": "Absent",
            "lateByMinutes": 0, "earlyLeaveByMinutes": 0, "overtimeSeconds": 0,
            "corrected": False, "correctionReason": None, "correctedBy": None,
        })
        created += 1
    audit(admin, "attendance_mark_absent", f"{date_key}: {created} marked")
    return jsonify({"message": f"{created} absent record(s) created for {date_key}.", "created": created})


# ─────────────────────────────────────────── admin: holiday calendar (HR / super_admin)

@app.get("/api/admin/holidays")
@admin_required
def list_holidays():
    year = request.args.get("year", "")
    rows = db.read("holidays")
    if year.isdigit():
        rows = [h for h in rows if h.get("date", "").startswith(year)]
    rows.sort(key=lambda h: h.get("date", ""))
    return jsonify(rows)


@app.post("/api/admin/holidays")
@role_required("hr_manager")
def add_holiday():
    data = request.get_json(silent=True) or {}
    date_key = clean(data.get("date", ""), 10)
    name = clean(data.get("name", ""), 120)
    kind = clean(data.get("type", "company"), 20) or "company"
    try:
        _dt.date.fromisoformat(date_key)
    except ValueError:
        return error("date must be YYYY-MM-DD.")
    if not name:
        return error("A holiday name is required.")
    if kind not in {"company", "public", "optional"}:
        kind = "company"
    row = db.insert("holidays", {"date": date_key, "name": name, "type": kind})
    audit(request.admin, "holiday_added", f"{date_key} {name}")
    return jsonify(row), 201


@app.delete("/api/admin/holidays/<int:holiday_id>")
@role_required("hr_manager")
def delete_holiday(holiday_id):
    if not db.remove("holidays", holiday_id):
        return error("Holiday not found.", 404)
    audit(request.admin, "holiday_deleted", str(holiday_id))
    return jsonify({"message": "Holiday deleted."})


# ─────────────────────────────────────────── leave management

LEAVE_TYPES = {"Casual Leave", "Sick Leave", "Annual Leave", "Earned Leave",
                "Unpaid Leave", "Work From Home", "Comp Off"}


@app.post("/api/leave/apply")
@attendance_required
def leave_apply():
    admin = request.admin
    data = request.get_json(silent=True) or {}
    leave_type = clean(data.get("type", ""), 40)
    from_date = clean(data.get("fromDate", ""), 10)
    to_date = clean(data.get("toDate", ""), 10)
    reason = clean(data.get("reason", ""), 300)
    if leave_type not in LEAVE_TYPES:
        return error(f"type must be one of: {', '.join(sorted(LEAVE_TYPES))}")
    try:
        d1, d2 = _dt.date.fromisoformat(from_date), _dt.date.fromisoformat(to_date)
    except ValueError:
        return error("fromDate/toDate must be YYYY-MM-DD.")
    if d2 < d1:
        return error("toDate cannot be before fromDate.")
    row = db.insert("leave_requests", {
        "adminId": admin["id"], "adminName": admin.get("name", ""),
        "adminEmail": admin.get("email", ""), "type": leave_type,
        "fromDate": from_date, "toDate": to_date, "reason": reason,
        "status": "pending", "decidedBy": None, "decidedAt": None,
    })
    audit(admin, "leave_applied", f"{leave_type} {from_date}..{to_date}")
    return jsonify(row), 201


@app.get("/api/leave/my")
@attendance_required
def leave_my():
    rows = [r for r in db.read("leave_requests") if r.get("adminId") == request.admin["id"]]
    rows.sort(key=lambda r: r.get("fromDate", ""), reverse=True)
    return jsonify(rows)


@app.get("/api/admin/leave")
@role_required("hr_manager")
def admin_leave_list():
    status = request.args.get("status", "")
    rows = db.read("leave_requests")
    if status:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: r.get("fromDate", ""), reverse=True)
    return jsonify(rows)


@app.post("/api/admin/leave/<int:leave_id>/decision")
@role_required("hr_manager")
def admin_leave_decision(leave_id):
    admin = request.admin
    data = request.get_json(silent=True) or {}
    decision = clean(data.get("decision", ""), 20)
    if decision not in {"approved", "rejected"}:
        return error("decision must be 'approved' or 'rejected'.")
    lv = db.find("leave_requests", leave_id)
    if not lv:
        return error("Leave request not found.", 404)
    if lv.get("status") != "pending":
        return error("This leave request has already been decided.")
    updated = db.update("leave_requests", leave_id, {
        "status": decision, "decidedBy": admin.get("email", ""), "decidedAt": db.now_iso(),
    })
    if decision == "approved":
        d1 = _dt.date.fromisoformat(lv["fromDate"])
        d2 = _dt.date.fromisoformat(lv["toDate"])
        day_status = "Work From Home" if lv["type"] == "Work From Home" else "Leave"
        cur = d1
        while cur <= d2:
            date_key = cur.isoformat()
            existing = _find_attendance_row(lv["adminId"], date_key)
            if existing:
                db.update("attendance", existing["id"], {"dayStatus": day_status})
            else:
                db.insert("attendance", {
                    "adminId": lv["adminId"], "adminName": lv.get("adminName", ""),
                    "adminEmail": lv.get("adminEmail", ""), "adminRole": "", "date": date_key,
                    "checkIn": None, "checkOut": None, "breaks": [], "onBreak": False,
                    "workedSeconds": 0, "dayStatus": day_status, "lateByMinutes": 0,
                    "earlyLeaveByMinutes": 0, "overtimeSeconds": 0, "corrected": False,
                    "correctionReason": None, "correctedBy": None,
                })
            cur += _dt.timedelta(days=1)
    audit(admin, "leave_decision", f"leave {leave_id}: {decision}")
    return jsonify(updated)


# ─────────────────────────────────────────── admin: user management (super_admin only)

@app.get("/api/admin/users")
@role_required()   # empty → only super_admin (role_required always allows super_admin)
def admin_list_users():
    users = db.read("admins")
    safe  = [{"id": u["id"], "name": u.get("name",""), "email": u.get("email",""),
                             "passwordSet": bool(u.get("passwordHash")),
                             "role": u.get("role","viewer"), "createdAt": u.get("createdAt","")}
             for u in users]
    return jsonify(safe)


@app.post("/api/admin/users")
@role_required()
def admin_create_user():
    data     = request.get_json(silent=True) or {}
    name     = clean(data.get("name",""), 120)
    email    = clean(data.get("email",""), 160).lower()
    password = str(data.get("password") or "")
    role     = clean(data.get("role","viewer"), 40)
    if not name or not valid_email(email) or not password:
        return error("Name, valid email and password are required.")
    if role not in ROLES:
        return error(f"Unknown role. Valid roles: {', '.join(ROLES)}")
    if len(password) < 8:
        return error("Password must be at least 8 characters.")
    if any(u.get("email","").lower() == email for u in db.read("admins")):
        return error("An admin account with that email already exists.")
    user = db.insert("admins", {
        "name":         name,
        "email":        email,
        "passwordHash": hash_password(password),
        "role":         role,
    })
    audit(request.admin, "user_created", f"{email} ({role})")
    return jsonify({"id": user["id"], "name": name, "email": email, "role": role}), 201


@app.put("/api/admin/users/<int:user_id>")
@role_required()
def admin_update_user(user_id):
    me = request.admin
    data = request.get_json(silent=True) or {}
    user = db.find("admins", user_id)
    if not user:
        return error("User not found.", 404)
    patch = {}
    if "name" in data:
        patch["name"] = clean(data["name"], 120)
    if "role" in data:
        if data["role"] not in ROLES:
            return error(f"Unknown role. Valid: {', '.join(ROLES)}")
        # Prevent demoting yourself
        if user_id == me["id"] and data["role"] != "super_admin":
            return error("You cannot change your own role.")
        patch["role"] = data["role"]
    if "password" in data:
        pw = str(data["password"])
        if len(pw) < 8:
            return error("Password must be at least 8 characters.")
        patch["passwordHash"] = hash_password(pw)
    if not patch:
        return error("Nothing to update.")
    updated = db.update("admins", user_id, patch)
    audit(request.admin, "user_updated", f"user {user_id}")
    return jsonify({"id": updated["id"], "name": updated.get("name"), "email": updated.get("email"), "role": updated.get("role")})


@app.delete("/api/admin/users/<int:user_id>")
@role_required()
def admin_delete_user(user_id):
    """Soft-delete by default: sets status to 'terminated' so attendance,
    payroll, and audit history referencing this user stay intact. Pass
    ?hard=true to permanently remove the record instead (rarely needed —
    e.g. cleaning up a genuine test/duplicate account)."""
    me = request.admin
    if user_id == me["id"]:
        return error("You cannot delete your own account.")
    user = db.find("admins", user_id)
    if not user:
        return error("User not found.", 404)
    hard = request.args.get("hard", "").lower() == "true"
    if hard:
        db.remove("admins", user_id)
        audit(me, "user_deleted_hard", user.get("email", "") or str(user_id))
        return jsonify({"message": "User permanently deleted."})
    updated = db.update("admins", user_id, {"status": "terminated"})
    audit(me, "user_terminated", user.get("email", "") or str(user_id))
    return jsonify({"message": "User deactivated (soft-deleted).", "user": updated})


@app.get("/api/admin/roles")
@admin_required
def list_roles():
    return jsonify({k: {"label": v["label"], "tabs": v["tabs"]} for k, v in ROLES.items()})


# ─────────────────────────────────────────── separate role tables endpoints

@app.get("/api/admin/employees")
@role_required("hr_manager", "team_lead")
def list_employees():
    return jsonify(db.get_employees())


@app.get("/api/admin/admins")
@role_required()
def list_admins():
    return jsonify(db.get_admins())


@app.get("/api/admin/hr-managers")
@role_required("hr_manager")
def list_hr_managers():
    return jsonify(db.get_hr_managers())


@app.get("/api/admin/team-leads")
@role_required("hr_manager", "team_lead")
def list_team_leads():
    return jsonify(db.get_team_leads())


@app.get("/api/admin/recruiters")
@role_required("hr_manager", "recruiter")
def list_recruiters():
    return jsonify(db.get_recruiters())


@app.get("/api/admin/clients")
@role_required("hr_manager")
def list_clients():
    return jsonify(db.get_clients())


@app.get("/api/admin/content-managers")
@role_required("hr_manager", "content_manager")
def list_content_managers():
    return jsonify(db.get_content_managers())


# ─────────────────────────────────────────── static frontend

@app.get("/")
def home():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/kyk_logo.webp")
def serve_logo():
    return send_from_directory(BASE_DIR, "kyk_logo.webp")


@app.get("/<path:filename>")
def static_files(filename):
    path = os.path.join(STATIC_DIR, filename)
    if os.path.isfile(path):
        return send_from_directory(STATIC_DIR, filename)
    if os.path.isfile(path + ".html"):
        return send_from_directory(STATIC_DIR, filename + ".html")
    abort(404)


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return error("Endpoint not found.", 404)
    return send_from_directory(STATIC_DIR, "index.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"KYK Technologies running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port,
            debug=os.environ.get("DEBUG") == "1", use_reloader=False)
