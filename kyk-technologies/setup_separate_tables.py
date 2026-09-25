"""setup_separate_tables.py — Creates and populates separate individual database tables.

Creates dedicated tables for:
- users
- admins
- employees
- hr_managers
- team_leads
- recruiters
- clients
- content_managers

Migrates existing accounts from `records` (`collection='admins'`) into their
respective dedicated tables with all appropriate attributes and constraints.
"""

import os
import sys
import json
from datetime import datetime, timezone, date
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

ROLE_DEMO_DATA = {
    "super_admin": {
        "email": os.environ.get("ADMIN_EMAIL", "admin@kyktechnologies.com").lower(),
        "name": "KYK Super Admin",
        "department": "Executive Leadership",
        "access_level": "all",
    },
    "hr_manager": {
        "email": "hr.manager@kyktechnologies.com",
        "name": "Demo HR Manager",
        "phone": "+91 98765 43210",
        "department": "Human Resources",
        "office_location": "Warangal, IN",
        "can_manage_attendance": True,
        "can_manage_payroll": True,
    },
    "recruiter": {
        "email": "recruiter@kyktechnologies.com",
        "name": "Demo Recruiter",
        "phone": "+91 98765 43211",
        "specialization": "Technical & Global Sourcing",
        "assigned_region": "Global Markets",
        "target_hires_per_quarter": 20,
    },
    "team_lead": {
        "email": "team.lead@kyktechnologies.com",
        "name": "Demo Team Lead",
        "phone": "+91 98765 43212",
        "department": "Software & Web Services",
        "team_name": "Core Platform & SaaS",
        "max_team_size": 12,
    },
    "employee": {
        "email": "employee@kyktechnologies.com",
        "name": "Demo Employee",
        "phone": "+91 98765 43213",
        "employee_code": "KYK-EMP-001",
        "department": "Software & Web Services",
        "designation": "Full-Stack Engineer",
        "employment_type": "Full-time",
        "attendance_eligible": True,
        "status": "active",
    },
    "client": {
        "email": "client@kyktechnologies.com",
        "client_name": "Demo Client",
        "company_name": "Apex Global Ventures",
        "phone": "+1 415 555 0199",
        "industry": "Enterprise Software / FinTech",
        "billing_address": "100 Montgomery St, Suite 1400, San Francisco, CA 94104",
        "contract_status": "active",
    },
    "content_manager": {
        "email": "content.manager@kyktechnologies.com",
        "name": "Demo Content Manager",
        "phone": "+91 98765 43214",
        "department": "Marketing & Content",
    },
}


def create_and_populate_separate_tables():
    print("=" * 70)
    print("Initializing Separate Relational Tables in Neon PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Create users table
        print("Creating table: users...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(150) NOT NULL,
                role VARCHAR(50) NOT NULL,
                phone VARCHAR(50),
                status VARCHAR(50) DEFAULT 'active' NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
            CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
        """)

        # 2. Create admins table
        print("Creating table: admins...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                is_super_admin BOOLEAN DEFAULT TRUE NOT NULL,
                department VARCHAR(100) DEFAULT 'Executive',
                access_level VARCHAR(50) DEFAULT 'all',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_admins_email ON admins (email);
        """)

        # 3. Create employees table
        print("Creating table: employees...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                employee_code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                department VARCHAR(100) DEFAULT 'Software & Web Services',
                designation VARCHAR(100) DEFAULT 'Software Engineer',
                employment_type VARCHAR(50) DEFAULT 'Full-time',
                joining_date DATE DEFAULT CURRENT_DATE,
                attendance_eligible BOOLEAN DEFAULT TRUE NOT NULL,
                status VARCHAR(50) DEFAULT 'active' NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_employees_email ON employees (email);
            CREATE INDEX IF NOT EXISTS idx_employees_code ON employees (employee_code);
        """)

        # 4. Create hr_managers table
        print("Creating table: hr_managers...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hr_managers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                department VARCHAR(100) DEFAULT 'Human Resources',
                office_location VARCHAR(100) DEFAULT 'Warangal, IN',
                can_manage_attendance BOOLEAN DEFAULT TRUE NOT NULL,
                can_manage_payroll BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_hr_managers_email ON hr_managers (email);
        """)

        # 5. Create team_leads table
        print("Creating table: team_leads...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_leads (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                department VARCHAR(100) DEFAULT 'Software & Web Services',
                team_name VARCHAR(100) DEFAULT 'Core Engineering',
                max_team_size INTEGER DEFAULT 10,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_team_leads_email ON team_leads (email);
        """)

        # 6. Create recruiters table
        print("Creating table: recruiters...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recruiters (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                specialization VARCHAR(100) DEFAULT 'Technical & Global Sourcing',
                assigned_region VARCHAR(100) DEFAULT 'Global',
                target_hires_per_quarter INTEGER DEFAULT 15,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_recruiters_email ON recruiters (email);
        """)

        # 7. Create clients table
        print("Creating table: clients...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                client_name VARCHAR(150) NOT NULL,
                company_name VARCHAR(200),
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                industry VARCHAR(100) DEFAULT 'Technology',
                billing_address TEXT,
                contract_status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_clients_email ON clients (email);
        """)

        # 8. Create content_managers table
        print("Creating table: content_managers...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS content_managers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(50),
                department VARCHAR(100) DEFAULT 'Marketing & Content',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_content_managers_email ON content_managers (email);
        """)

        # 9. Add login tracking columns to users and admins
        print("Ensuring login tracking columns on users & admins...")
        cur.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(50);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;
            ALTER TABLE admins ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
            ALTER TABLE admins ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(50);
            ALTER TABLE admins ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;
        """)

        # 10. Create dedicated jobs table
        print("Creating table: jobs...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                department VARCHAR(120) NOT NULL,
                location VARCHAR(120) NOT NULL,
                type VARCHAR(50) DEFAULT 'Full-time',
                level VARCHAR(50) DEFAULT 'Mid-level',
                description TEXT,
                requirements JSONB,
                active BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_department ON jobs (department);
            CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs (active);
        """)

        # 11. Create dedicated applications table
        print("Creating table: applications...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id SERIAL PRIMARY KEY,
                job_id INTEGER,
                job_title VARCHAR(200),
                name VARCHAR(150) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                status VARCHAR(50) DEFAULT 'applied',
                notes TEXT,
                resume_filename VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_applications_email ON applications (email);
            CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
        """)

        # 12. Create dedicated attendance table
        print("Creating table: attendance...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                user_name VARCHAR(150),
                user_email VARCHAR(255),
                user_role VARCHAR(50),
                date VARCHAR(20) NOT NULL,
                check_in VARCHAR(50),
                check_out VARCHAR(50),
                worked_seconds INTEGER DEFAULT 0,
                day_status VARCHAR(50) DEFAULT 'present',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_attendance_user_email ON attendance (user_email);
            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (date);
        """)

        # 13. Create dedicated audit_logs table
        print("Creating table: audit_logs...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER,
                admin_email VARCHAR(255),
                admin_role VARCHAR(50),
                action VARCHAR(100) NOT NULL,
                detail TEXT,
                ip VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_email ON audit_logs (admin_email);
        """)

        # 14. Create dedicated sessions table
        print("Creating table: sessions...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                jti VARCHAR(100) UNIQUE NOT NULL,
                owner_type VARCHAR(50) NOT NULL,
                owner_id INTEGER NOT NULL,
                ip VARCHAR(50),
                ua VARCHAR(255),
                exp BIGINT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_jti ON sessions (jti);
            CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions (owner_type, owner_id);
        """)

        # 9. Migrate accounts from `records` where collection = 'admins' into `users` and specific tables
        print("Migrating and synchronizing accounts into separate tables...")
        cur.execute("SELECT id, data FROM records WHERE collection = 'admins';")
        rows = cur.fetchall()

        # Map existing accounts by email
        existing_accounts = {}
        for rec_id, data in rows:
            email = (data.get("email") or "").strip().lower()
            if email:
                existing_accounts[email] = {
                    "id": rec_id,
                    "email": email,
                    "name": data.get("name", "User"),
                    "role": data.get("role", "viewer"),
                    "passwordHash": data.get("passwordHash") or hash_password("KYKUser@2026"),
                }

        # Ensure demo accounts from ROLE_DEMO_DATA also exist
        demo_pw_hash = hash_password(os.environ.get("DEMO_PASSWORD", "KYKUser@2026"))
        admin_pw_hash = hash_password(os.environ.get("ADMIN_PASSWORD", "KYKAdmin@2026"))

        for role, d_info in ROLE_DEMO_DATA.items():
            e = d_info["email"].lower()
            if e not in existing_accounts:
                existing_accounts[e] = {
                    "id": len(existing_accounts) + 1,
                    "email": e,
                    "name": d_info.get("name") or d_info.get("client_name", "Demo User"),
                    "role": role,
                    "passwordHash": admin_pw_hash if role == "super_admin" else demo_pw_hash,
                }

        # Populate users table
        emp_seq = 1
        for email, acc in existing_accounts.items():
            cur.execute("""
                INSERT INTO users (email, password_hash, name, role, status)
                VALUES (%s, %s, %s, %s, 'active')
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, (email, acc["passwordHash"], acc["name"], acc["role"]))
            user_id = cur.fetchone()[0]

            role = acc["role"]
            name = acc["name"]

            # Role-specific table population
            if role == "super_admin":
                info = ROLE_DEMO_DATA.get("super_admin", {})
                cur.execute("""
                    INSERT INTO admins (user_id, name, email, is_super_admin, department, access_level)
                    VALUES (%s, %s, %s, TRUE, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, name, email, info.get("department", "Executive"), info.get("access_level", "all")))

            elif role == "employee":
                info = ROLE_DEMO_DATA.get("employee", {})
                code = info.get("employee_code", f"KYK-EMP-{emp_seq:03d}")
                cur.execute("""
                    INSERT INTO employees (user_id, employee_code, name, email, phone, department, designation, employment_type, attendance_eligible, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'active')
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, code, name, email, info.get("phone", "+91 98765 43213"),
                      info.get("department", "Software & Web Services"),
                      info.get("designation", "Software Engineer"),
                      info.get("employment_type", "Full-time")))
                emp_seq += 1

            elif role == "hr_manager":
                info = ROLE_DEMO_DATA.get("hr_manager", {})
                cur.execute("""
                    INSERT INTO hr_managers (user_id, name, email, phone, department, office_location, can_manage_attendance, can_manage_payroll)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, TRUE)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, name, email, info.get("phone", "+91 98765 43210"),
                      info.get("department", "Human Resources"),
                      info.get("office_location", "Warangal, IN")))

            elif role == "team_lead":
                info = ROLE_DEMO_DATA.get("team_lead", {})
                cur.execute("""
                    INSERT INTO team_leads (user_id, name, email, phone, department, team_name, max_team_size)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, name, email, info.get("phone", "+91 98765 43212"),
                      info.get("department", "Software & Web Services"),
                      info.get("team_name", "Core Platform & SaaS"),
                      info.get("max_team_size", 12)))

            elif role == "recruiter":
                info = ROLE_DEMO_DATA.get("recruiter", {})
                cur.execute("""
                    INSERT INTO recruiters (user_id, name, email, phone, specialization, assigned_region, target_hires_per_quarter)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, name, email, info.get("phone", "+91 98765 43211"),
                      info.get("specialization", "Technical & Global Sourcing"),
                      info.get("assigned_region", "Global Markets"),
                      info.get("target_hires_per_quarter", 20)))

            elif role == "client":
                info = ROLE_DEMO_DATA.get("client", {})
                c_name = info.get("client_name") or name
                cur.execute("""
                    INSERT INTO clients (user_id, client_name, company_name, email, phone, industry, billing_address, contract_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        client_name = EXCLUDED.client_name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, c_name, info.get("company_name", "Apex Global"), email,
                      info.get("phone", "+1 415 555 0199"), info.get("industry", "Enterprise Software"),
                      info.get("billing_address", "100 Montgomery St, San Francisco, CA"), "active"))

            elif role == "content_manager":
                info = ROLE_DEMO_DATA.get("content_manager", {})
                cur.execute("""
                    INSERT INTO content_managers (user_id, name, email, phone, department)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, name, email, info.get("phone", "+91 98765 43214"),
                      info.get("department", "Marketing & Content")))

        # 10. Populate jobs table from records if empty
        cur.execute("SELECT COUNT(*) FROM jobs;")
        if cur.fetchone()[0] == 0:
            cur.execute("SELECT id, data, created_at, updated_at FROM records WHERE collection = 'jobs' ORDER BY id;")
            job_records = cur.fetchall()
            print(f"Populating {len(job_records)} jobs into jobs table...")
            for jid, data, c_at, u_at in job_records:
                d = data if isinstance(data, dict) else json.loads(data or "{}")
                cur.execute("""
                    INSERT INTO jobs (id, title, department, location, type, level, description, requirements, active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        department = EXCLUDED.department,
                        location = EXCLUDED.location,
                        type = EXCLUDED.type,
                        level = EXCLUDED.level,
                        description = EXCLUDED.description,
                        requirements = EXCLUDED.requirements,
                        active = EXCLUDED.active,
                        updated_at = EXCLUDED.updated_at;
                """, (
                    jid,
                    d.get("title", "Job Title"),
                    d.get("department", "General"),
                    d.get("location", "Remote"),
                    d.get("type", "Full-time"),
                    d.get("level", "Mid-level"),
                    d.get("description", ""),
                    json.dumps(d.get("requirements", [])),
                    d.get("active", True),
                    c_at or datetime.now(timezone.utc),
                    u_at or datetime.now(timezone.utc),
                ))
            cur.execute("SELECT setval('jobs_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jobs));")

        # 11. Populate attendance table from records if empty
        cur.execute("SELECT COUNT(*) FROM attendance;")
        if cur.fetchone()[0] == 0:
            cur.execute("SELECT id, data, created_at, updated_at FROM records WHERE collection = 'attendance' ORDER BY id;")
            att_records = cur.fetchall()
            print(f"Populating {len(att_records)} attendance records into attendance table...")
            for aid, data, c_at, u_at in att_records:
                d = data if isinstance(data, dict) else json.loads(data or "{}")
                cur.execute("""
                    INSERT INTO attendance (id, user_id, user_name, user_email, user_role, date, check_in, check_out, worked_seconds, day_status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (
                    aid,
                    d.get("adminId"),
                    d.get("adminName"),
                    d.get("adminEmail"),
                    d.get("adminRole"),
                    str(d.get("date", "")),
                    d.get("checkIn"),
                    d.get("checkOut"),
                    int(d.get("workedSeconds") or 0),
                    d.get("dayStatus", "present"),
                    c_at or datetime.now(timezone.utc),
                    u_at or datetime.now(timezone.utc),
                ))
            cur.execute("SELECT setval('attendance_id_seq', (SELECT COALESCE(MAX(id), 1) FROM attendance));")

        # 12. Populate audit_logs table from records if empty
        cur.execute("SELECT COUNT(*) FROM audit_logs;")
        if cur.fetchone()[0] == 0:
            cur.execute("SELECT id, data, created_at FROM records WHERE collection = 'audit_log' ORDER BY id;")
            audit_records = cur.fetchall()
            print(f"Populating {len(audit_records)} audit logs into audit_logs table...")
            for lid, data, c_at in audit_records:
                d = data if isinstance(data, dict) else json.loads(data or "{}")
                cur.execute("""
                    INSERT INTO audit_logs (id, admin_id, admin_email, admin_role, action, detail, ip, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (
                    lid,
                    d.get("adminId"),
                    d.get("adminEmail"),
                    d.get("adminRole"),
                    d.get("action", "action"),
                    d.get("detail", ""),
                    d.get("ip", ""),
                    c_at or datetime.now(timezone.utc),
                ))
            cur.execute("SELECT setval('audit_logs_id_seq', (SELECT COALESCE(MAX(id), 1) FROM audit_logs));")

        conn.commit()
        print("Successfully committed all separate tables and initial records!")

        # 13. Print Table Count Summary
        tables = ["users", "admins", "employees", "hr_managers", "team_leads", "recruiters", "clients", "content_managers", "jobs", "applications", "attendance", "audit_logs", "sessions"]
        print("\n" + "=" * 50)
        print("DATABASE SUMMARY (Separate Individual Tables):")
        print("=" * 50)
        for tbl in tables:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            cnt = cur.fetchone()[0]
            print(f"  Table '{tbl:<18}': {cnt} row(s)")
        print("=" * 50)

    except Exception as e:
        conn.rollback()
        print(f"Error initializing separate tables: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_and_populate_separate_tables()
