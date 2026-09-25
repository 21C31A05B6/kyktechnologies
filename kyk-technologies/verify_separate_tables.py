"""verify_separate_tables.py — Automated verification for separate individual database tables.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("DATABASE_URL missing")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


def test_tables_in_postgres():
    print("\n--- 1. Testing Neon PostgreSQL Direct Tables ---")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    required_tables = [
        "users",
        "admins",
        "employees",
        "hr_managers",
        "team_leads",
        "recruiters",
        "clients",
        "content_managers",
    ]

    for tbl in required_tables:
        cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        count = cur.fetchone()[0]
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' LIMIT 3;")
        cols = cur.fetchall()
        col_summary = ", ".join([f"{c[0]} ({c[1]})" for c in cols])
        print(f"  [OK] Table '{tbl}': {count} row(s) | Sample columns: {col_summary}")

    # Inspect sample employee
    cur.execute("SELECT id, name, email, employee_code, designation, department FROM employees LIMIT 1;")
    emp = cur.fetchone()
    print(f"  [Sample Employee]: ID={emp[0]}, Name='{emp[1]}', Code='{emp[3]}', Role='{emp[4]}'")

    # Inspect sample recruiter
    cur.execute("SELECT id, name, email, specialization FROM recruiters LIMIT 1;")
    rec = cur.fetchone()
    print(f"  [Sample Recruiter]: ID={rec[0]}, Name='{rec[1]}', Spec='{rec[3]}'")

    # Inspect sample client
    cur.execute("SELECT id, client_name, company_name, email FROM clients LIMIT 1;")
    cli = cur.fetchone()
    print(f"  [Sample Client]: ID={cli[0]}, Name='{cli[1]}', Company='{cli[2]}'")

    cur.close()
    conn.close()


def test_flask_endpoints_and_sync():
    print("\n--- 2. Testing Flask API Endpoints & Synchronization ---")
    from app import app

    client = app.test_client()

    # Login as Super Admin
    login_res = client.post("/api/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@kyktechnologies.com"),
        "password": os.environ.get("ADMIN_PASSWORD", "KYKAdmin@2026"),
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.data}"
    token = login_res.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  [OK] Logged in successfully as Super Admin.")

    # Test separate table endpoints
    endpoints = [
        ("/api/admin/employees", "employees"),
        ("/api/admin/admins", "admins"),
        ("/api/admin/hr-managers", "hr_managers"),
        ("/api/admin/team-leads", "team_leads"),
        ("/api/admin/recruiters", "recruiters"),
        ("/api/admin/clients", "clients"),
        ("/api/admin/content-managers", "content_managers"),
    ]

    for ep, name in endpoints:
        res = client.get(ep, headers=headers)
        assert res.status_code == 200, f"Failed GET {ep}: {res.status_code}"
        data = res.get_json()
        assert isinstance(data, list), f"Expected list from {ep}"
        print(f"  [OK] GET {ep:<28} -> {len(data)} record(s)")

    # Test creating a new user and verifying auto-sync to separate employee table
    print("\n--- 3. Testing Auto-Sync When Creating New Employee User ---")
    test_email = "test.engineer@kyktechnologies.com"
    create_res = client.post("/api/admin/users", headers=headers, json={
        "name": "Test Engineer",
        "email": test_email,
        "password": "Password123!",
        "role": "employee",
    })
    assert create_res.status_code == 201, f"Create user failed: {create_res.data}"
    created_user = create_res.get_json()
    created_id = created_user["id"]
    print(f"  [OK] Created user via /api/admin/users: ID={created_id}, Email={test_email}")

    # Verify present in GET /api/admin/employees
    emp_res = client.get("/api/admin/employees", headers=headers)
    emp_list = emp_res.get_json()
    matching_emp = next((e for e in emp_list if e.get("email") == test_email), None)
    assert matching_emp is not None, "New user was not synced into employees table!"
    print(f"  [OK] Verified employee table sync: Code={matching_emp.get('employeeCode')}, Name='{matching_emp.get('name')}'")

    # Clean up test user (hard delete to test cascade removal)
    del_res = client.delete(f"/api/admin/users/{created_id}?hard=true", headers=headers)
    assert del_res.status_code == 200, f"Delete failed: {del_res.data}"
    print(f"  [OK] Cleaned up test user ID={created_id}.")

    # Verify deleted from employees table
    emp_res_after = client.get("/api/admin/employees", headers=headers)
    assert not any(e.get("email") == test_email for e in emp_res_after.get_json()), "Employee was not removed after user deletion!"
    print("  [OK] Verified cascade removal from employees table.")


if __name__ == "__main__":
    test_tables_in_postgres()
    test_flask_endpoints_and_sync()
    print("\n" + "=" * 50)
    print("ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 50)
