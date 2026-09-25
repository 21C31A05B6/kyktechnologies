"""setup_neon_db.py — Initializes and seeds Neon PostgreSQL database for KYK Technologies.

Creates:
1. `records` table used by db_sql.py (with performance indexes)
2. `roles` reference table with all role permissions and attendance requirements
3. Relational SQL Views (users, attendance, jobs, applications, talent, contacts, newsletter, insights, audit_log)
4. Populates roles, admin account, all demo user accounts per role, jobs, insights, and initial attendance.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("Error: DATABASE_URL not set in .env")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

import psycopg2
from security import hash_password
from seed import JOBS, INSIGHTS, ROLES, ATTENDANCE_ROLES

ROLE_DETAILS = {
    "super_admin": {
        "label": "Super Admin",
        "description": "Full administrative access to entire platform, jobs, candidates, user management, and org-wide attendance.",
        "tabs": ROLES["super_admin"]["tabs"],
        "attendance_eligible": False,
    },
    "hr_manager": {
        "label": "HR Manager",
        "description": "Manages talent pipeline, applications, contacts, applicant communications, and company attendance records.",
        "tabs": ROLES["hr_manager"]["tabs"],
        "attendance_eligible": True,
    },
    "recruiter": {
        "label": "Recruiter",
        "description": "Reviews job applications, candidate evaluations, talent pools, and candidate status tracking.",
        "tabs": ROLES["recruiter"]["tabs"],
        "attendance_eligible": True,
    },
    "team_lead": {
        "label": "Team Lead",
        "description": "Oversees department jobs, reviews technical applications, and monitors team tasks.",
        "tabs": ROLES["team_lead"]["tabs"],
        "attendance_eligible": True,
    },
    "content_manager": {
        "label": "Content Manager",
        "description": "Creates, edits, and manages blog insights, marketing content, and published articles.",
        "tabs": ROLES["content_manager"]["tabs"],
        "attendance_eligible": True,
    },
    "viewer": {
        "label": "Viewer",
        "description": "Read-only access to high-level statistics and dashboard metrics.",
        "tabs": ROLES["viewer"]["tabs"],
        "attendance_eligible": False,
    },
    "employee": {
        "label": "Employee",
        "description": "Internal staff member with daily attendance check-in/out, hours tracking, and calendar view.",
        "tabs": ROLES["employee"]["tabs"],
        "attendance_eligible": True,
    },
    "client": {
        "label": "Client",
        "description": "External client portal to view project status, team allocations, and requested services.",
        "tabs": ROLES["client"]["tabs"],
        "attendance_eligible": False,
    },
}

DEMO_USERS = {
    "hr_manager":      ("hr.manager@kyktechnologies.com",      "Demo HR Manager"),
    "recruiter":       ("recruiter@kyktechnologies.com",       "Demo Recruiter"),
    "content_manager": ("content.manager@kyktechnologies.com", "Demo Content Manager"),
    "team_lead":       ("team.lead@kyktechnologies.com",       "Demo Team Lead"),
    "employee":        ("employee@kyktechnologies.com",        "Demo Employee"),
    "viewer":          ("viewer@kyktechnologies.com",          "Demo Viewer"),
    "client":          ("client@kyktechnologies.com",          "Demo Client"),
}


def setup_database():
    print("=" * 70)
    print("Connecting to Neon PostgreSQL...")
    conn = psycopg2.connect(
        DATABASE_URL,
        connect_timeout=20,
    )
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Create records table (compatible with SQLAlchemy db_sql.py)
        print("Creating 'records' table and indexes...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS records (
                collection VARCHAR(64) NOT NULL,
                id INTEGER NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection, id)
            );

            CREATE INDEX IF NOT EXISTS idx_records_collection ON records (collection);
            CREATE INDEX IF NOT EXISTS idx_records_created_at ON records (created_at);
            CREATE INDEX IF NOT EXISTS idx_records_data ON records USING gin (data);
        """)

        # 2. Create roles reference table
        print("Creating 'roles' reference table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                role VARCHAR(50) PRIMARY KEY,
                label VARCHAR(100) NOT NULL,
                description TEXT,
                tabs JSONB NOT NULL,
                attendance_eligible BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Populate roles
        print("Populating roles...")
        for role_key, info in ROLE_DETAILS.items():
            cur.execute("""
                INSERT INTO roles (role, label, description, tabs, attendance_eligible)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (role) DO UPDATE SET
                    label = EXCLUDED.label,
                    description = EXCLUDED.description,
                    tabs = EXCLUDED.tabs,
                    attendance_eligible = EXCLUDED.attendance_eligible;
            """, (
                role_key,
                info["label"],
                info["description"],
                json.dumps(info["tabs"]),
                info["attendance_eligible"]
            ))

        # 3. Create relational views over JSONB records for direct SQL visibility
        print("Creating relational SQL Views...")
        cur.execute("""
            CREATE OR REPLACE VIEW view_users AS
            SELECT 
                id,
                data->>'email' AS email,
                data->>'name' AS name,
                data->>'role' AS role,
                data->>'passwordHash' AS password_hash,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'admins'
            ORDER BY id;

            CREATE OR REPLACE VIEW view_attendance AS
            SELECT 
                id,
                (data->>'adminId')::int AS user_id,
                data->>'adminName' AS user_name,
                data->>'adminEmail' AS user_email,
                data->>'adminRole' AS user_role,
                data->>'date' AS date,
                data->>'checkIn' AS check_in,
                data->>'checkOut' AS check_out,
                (data->>'workedSeconds')::int AS worked_seconds,
                data->>'dayStatus' AS day_status,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'attendance'
            ORDER BY date DESC, id DESC;

            CREATE OR REPLACE VIEW view_jobs AS
            SELECT 
                id,
                data->>'title' AS title,
                data->>'department' AS department,
                data->>'location' AS location,
                data->>'type' AS type,
                data->>'level' AS level,
                data->>'description' AS description,
                data->'requirements' AS requirements,
                COALESCE((data->>'active')::boolean, true) AS active,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'jobs'
            ORDER BY id;

            CREATE OR REPLACE VIEW view_applications AS
            SELECT 
                id,
                (data->>'jobId')::int AS job_id,
                data->>'name' AS candidate_name,
                data->>'email' AS email,
                data->>'phone' AS phone,
                data->>'status' AS status,
                data->>'notes' AS notes,
                data->>'resumeFilename' AS resume_filename,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'applications'
            ORDER BY id DESC;

            CREATE OR REPLACE VIEW view_talent AS
            SELECT 
                id,
                data->>'name' AS candidate_name,
                data->>'email' AS email,
                data->>'phone' AS phone,
                data->>'role' AS target_role,
                data->>'skills' AS skills,
                data->>'status' AS stage,
                data->>'resumeFilename' AS resume_filename,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'talent'
            ORDER BY id DESC;

            CREATE OR REPLACE VIEW view_contacts AS
            SELECT 
                id,
                data->>'name' AS sender_name,
                data->>'email' AS email,
                data->>'subject' AS subject,
                data->>'message' AS message,
                COALESCE((data->>'read')::boolean, false) AS is_read,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'contacts'
            ORDER BY id DESC;

            CREATE OR REPLACE VIEW view_newsletter AS
            SELECT 
                id,
                data->>'email' AS email,
                created_at
            FROM records
            WHERE collection = 'newsletter'
            ORDER BY id;

            CREATE OR REPLACE VIEW view_insights AS
            SELECT 
                id,
                data->>'title' AS title,
                data->>'category' AS category,
                data->>'summary' AS summary,
                data->>'body' AS body,
                COALESCE((data->>'published')::boolean, false) AS published,
                created_at,
                updated_at
            FROM records
            WHERE collection = 'insights'
            ORDER BY id;

            CREATE OR REPLACE VIEW view_audit_log AS
            SELECT 
                id,
                (data->>'adminId')::int AS admin_id,
                data->>'adminEmail' AS admin_email,
                data->>'adminRole' AS admin_role,
                data->>'action' AS action,
                data->>'detail' AS detail,
                data->>'ip' AS ip_address,
                created_at
            FROM records
            WHERE collection = 'audit_log'
            ORDER BY id DESC;
        """)

        # 4. Helper function to insert into records
        def get_max_id(coll):
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM records WHERE collection = %s", (coll,))
            return cur.fetchone()[0]

        def insert_record(coll, record_id, body_dict):
            now = datetime.now(timezone.utc)
            cur.execute("""
                INSERT INTO records (collection, id, data, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (collection, id) DO UPDATE SET
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at;
            """, (coll, record_id, json.dumps(body_dict), now, now))

        # 5. Populate Jobs
        cur.execute("SELECT COUNT(*) FROM records WHERE collection = 'jobs';")
        if cur.fetchone()[0] == 0:
            print(f"Seeding {len(JOBS)} jobs...")
            for idx, job in enumerate(JOBS, start=1):
                insert_record("jobs", idx, job)

        # 6. Populate Insights
        cur.execute("SELECT COUNT(*) FROM records WHERE collection = 'insights';")
        if cur.fetchone()[0] == 0:
            print(f"Seeding {len(INSIGHTS)} insights...")
            for idx, ins in enumerate(INSIGHTS, start=1):
                insert_record("insights", idx, ins)

        # 7. Populate Super Admin & Demo Users
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@kyktechnologies.com").lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "KYKAdmin@2026")
        demo_password = os.environ.get("DEMO_PASSWORD", "KYKUser@2026")

        # Check existing admins
        cur.execute("SELECT id, data->>'email' FROM records WHERE collection = 'admins';")
        existing_admins = {row[1].lower(): row[0] for row in cur.fetchall() if row[1]}

        # Insert / update Super Admin
        if admin_email not in existing_admins:
            next_id = get_max_id("admins") + 1
            insert_record("admins", next_id, {
                "email": admin_email,
                "passwordHash": hash_password(admin_password),
                "name": "KYK Super Admin",
                "role": "super_admin",
            })
            existing_admins[admin_email] = next_id
            print(f"Created Super Admin: {admin_email}")
        else:
            print(f"Super Admin already exists: {admin_email}")

        # Insert Demo Users
        for role, (d_email, d_name) in DEMO_USERS.items():
            if d_email.lower() not in existing_admins:
                next_id = get_max_id("admins") + 1
                insert_record("admins", next_id, {
                    "email": d_email,
                    "passwordHash": hash_password(demo_password),
                    "name": d_name,
                    "role": role,
                })
                existing_admins[d_email.lower()] = next_id
                print(f"Created role account [{role}]: {d_email}")
            else:
                print(f"Role account [{role}] already exists: {d_email}")

        # 8. Populate Sample Attendance for demo employees
        cur.execute("SELECT COUNT(*) FROM records WHERE collection = 'attendance';")
        if cur.fetchone()[0] == 0:
            print("Seeding realistic sample attendance data...")
            emp_id = existing_admins.get("employee@kyktechnologies.com")
            hr_id = existing_admins.get("hr.manager@kyktechnologies.com")
            tl_id = existing_admins.get("team.lead@kyktechnologies.com")

            now_dt = datetime.now(timezone.utc)
            att_id = 1

            sample_users = [
                (emp_id, "Demo Employee", "employee@kyktechnologies.com", "employee"),
                (hr_id, "Demo HR Manager", "hr.manager@kyktechnologies.com", "hr_manager"),
                (tl_id, "Demo Team Lead", "team.lead@kyktechnologies.com", "team_lead"),
            ]

            for u_id, u_name, u_email, u_role in sample_users:
                if not u_id:
                    continue
                # Create attendance for past 5 business days
                for day_offset in range(5, 0, -1):
                    day = now_dt - timedelta(days=day_offset)
                    # skip weekends
                    if day.weekday() >= 5:
                        continue
                    date_str = day.strftime("%Y-%m-%d")
                    checkin_dt = day.replace(hour=9, minute=0, second=0, microsecond=0)
                    checkout_dt = day.replace(hour=18, minute=15, second=0, microsecond=0)
                    worked_seconds = int((checkout_dt - checkin_dt).total_seconds())

                    insert_record("attendance", att_id, {
                        "adminId": u_id,
                        "adminName": u_name,
                        "adminEmail": u_email,
                        "adminRole": u_role,
                        "date": date_str,
                        "checkIn": checkin_dt.isoformat(),
                        "checkOut": checkout_dt.isoformat(),
                        "workedSeconds": worked_seconds,
                        "dayStatus": "Full Day",
                    })
                    att_id += 1

            print(f"Seeded {att_id - 1} sample attendance records.")

        conn.commit()
        print("Database schema and data successfully committed!")

    except Exception as e:
        conn.rollback()
        print(f"Database setup error: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    setup_database()
    from setup_separate_tables import create_and_populate_separate_tables
    create_and_populate_separate_tables()
