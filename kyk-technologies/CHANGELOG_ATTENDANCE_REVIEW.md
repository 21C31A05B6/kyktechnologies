# Changelog — critical fixes + attendance features (this revision)

Applied directly on top of the existing codebase, same JSON/SQL dispatcher
pattern (`db.py`) and same route style throughout. Nothing was restructured.

## ⚠️ Action required from you — not fixable in code
- **Rotate every credential that was in `.env`** (DB password, `SECRET_KEY`,
  admin/demo passwords). It shipped inside the project ZIP, so treat it as
  compromised regardless of `.gitignore`. Use `.env.example` (new) as the
  template for the new `.env` — never zip/commit the real one.

## Critical fixes
- **Timezone bug**: attendance dates and late/early/overtime math were
  computed in UTC; now use `COMPANY_TIMEZONE` (default `Asia/Kolkata`,
  see `.env.example`). `app.py`: `_today_key()`, `_to_local()`, `_shift_dt()`.
- **Role-change sync bug** (`db_sql.py`, `_sync_user_insert_or_update`):
  changing a user's role now deletes the *old* role-specific profile row
  (e.g. `employees`) in the same transaction as creating the new one
  (e.g. `hr_managers`), so switching roles can no longer leave a stale
  row behind.
- **Rate limiter** (`app.py`, `rate_limit()`): now backed by Redis when
  `REDIS_URL` is set, so limits are enforced across every Gunicorn
  worker instead of per-process. Falls back to the original in-process
  dict when unset (fine for single-worker/dev only).
- **No account-status enforcement**: login now rejects
  `suspended`/`terminated`/`inactive` accounts, and an already-issued
  token for such an account is rejected immediately too (not just at
  next login) — `current_admin()` in `app.py`.
- **No soft-delete**: `DELETE /api/admin/users/<id>` now sets
  `status=terminated` by default, preserving attendance/audit history.
  Pass `?hard=true` for the old permanent-delete behavior.
- **No database migrations**: Alembic scaffolded (`alembic.ini`,
  `migrations/`). `db_sql.py`'s own `create_all()` calls are unchanged
  (see the baseline migration's docstring for how the two coexist and
  how to fully hand schema ownership to Alembic later).

## Attendance features added (all in `app.py`)
- **Break tracking**: `POST /api/attendance/break/start`,
  `POST /api/attendance/break/end`. Worked hours exclude break time.
- **Late / Early Leave / Overtime / Absent / Holiday / Weekend / Leave /
  Work From Home status**: computed per shift config (`SHIFT_START`,
  `SHIFT_END`, `LATE_GRACE_MINUTES`, `EARLY_LEAVE_GRACE_MINUTES`,
  `WEEKEND_DAYS` — see `.env.example`).
- **Absent records**: `POST /api/admin/attendance/mark-absent` backfills
  explicit `Absent` rows for a date, so "no punch" and "Absent" are
  distinguishable in reports. Idempotent.
- **HR attendance correction**: `POST /api/admin/attendance/<id>/correct`
  — reason + approver required, recalculates hours/status, keeps
  original values (`originalCheckIn`/`originalCheckOut`).
- **Holiday calendar**: `GET/POST /api/admin/holidays`,
  `DELETE /api/admin/holidays/<id>`. Attendance/absent logic checks it.
- **Leave management**: `POST /api/leave/apply`, `GET /api/leave/my`,
  `GET /api/admin/leave`, `POST /api/admin/leave/<id>/decision`. Approval
  auto-populates the employee's attendance for that date range.
- **Attendance CSV export**: `GET /api/admin/attendance/export.csv`.
- **Richer summaries** on `/api/attendance/calendar` and
  `/api/admin/attendance` (late/absent/leave counts, overtime hours,
  average worked hours).
- **Audit log** extended with every new action above (`attendance_break_start`,
  `attendance_correction`, `attendance_mark_absent`, `holiday_added`,
  `leave_applied`, `leave_decision`, `login_blocked`, `user_terminated`, ...).

All of the above was exercised against a live run of the app (checkin →
break → checkout → holiday → leave → CSV export → soft-delete →
login-blocked), not just reviewed by reading the code.

## Explicitly NOT done in this pass
These need infrastructure/credentials or product decisions I can't make
for you, and folding them in now would mean shipping something half-built:
cloud file storage (S3/R2) for resumes, Celery/Redis-backed email queue,
payroll, the full ATS pipeline overhaul, expanding the AI assistant to a
real LLM, 2FA, malware scanning (ClamAV), multi-tenant architecture, and
an automated test suite. Happy to take on any of these next — each is
realistically its own focused pass.
