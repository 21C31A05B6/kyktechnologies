"""Comprehensive End-to-End Test Suite for KYK Technologies HRMS Portal
Tests all 4 roles (Admin, HR Manager, Team Lead / Manager, Employee) across all 12 modules.
"""

import pytest
import json
from app import app
import db

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.get_data(as_text=True)}"
    data = res.get_json()
    assert "token" in data
    return data["token"], data

def test_01_admin_role_and_governance(client):
    token, auth_data = login(client, "admin@kyktechnologies.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Profile & RBAC
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] in {"super_admin", "admin"}
    assert "departments" in me["tabs"]
    assert "payroll" in me["tabs"]
    assert "audit_log" in me["tabs"]

    # 2. Departments & Branches
    depts_res = client.get("/api/org/departments", headers=headers)
    assert depts_res.status_code == 200
    depts = depts_res.get_json()
    assert len(depts) >= 1

    branches_res = client.get("/api/org/branches", headers=headers)
    assert branches_res.status_code == 200
    branches = branches_res.get_json()
    assert len(branches) >= 1

    # 3. Analytics Summary & Audit Logs
    rep_res = client.get("/api/reports/analytics-summary", headers=headers)
    assert rep_res.status_code == 200
    rep = rep_res.get_json()
    assert "totalEmployees" in rep
    assert "monthlyPayrollCost" in rep

    audit_res = client.get("/api/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    assert len(audit_res.get_json()) >= 1

def test_02_hr_manager_operations(client):
    token, auth_data = login(client, "hr.manager@kyktechnologies.com", "Hr@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify HR profile
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] in {"hr_manager", "hr"}

    # 2. Recruitment & Candidate List
    apps_res = client.get("/api/admin/applications", headers=headers)
    assert apps_res.status_code == 200

    # 3. Onboarding Tasks
    onb_res = client.get("/api/onboarding/tasks", headers=headers)
    assert onb_res.status_code == 200
    tasks = onb_res.get_json()
    assert len(tasks) >= 1

    # 4. Payroll Runs & Generation
    runs_res = client.get("/api/payroll/runs", headers=headers)
    assert runs_res.status_code == 200

    # 5. Leave List
    leaves_res = client.get("/api/admin/leave", headers=headers)
    assert leaves_res.status_code == 200

def test_03_manager_team_workflow(client):
    token, auth_data = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Manager profile
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] in {"team_lead", "manager"}

    # 2. Team Members
    team_res = client.get("/api/manager/team", headers=headers)
    assert team_res.status_code == 200
    team = team_res.get_json()
    assert len(team) >= 1

    # 3. Team Timesheets & Goals
    ts_res = client.get("/api/manager/timesheets", headers=headers)
    assert ts_res.status_code == 200

    goals_res = client.get("/api/performance/team-goals", headers=headers)
    assert goals_res.status_code == 200

def test_04_employee_self_service(client):
    token, auth_data = login(client, "employee@kyktechnologies.com", "Emp@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Employee profile
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] == "employee"

    # 2. Attendance punch
    att_today = client.get("/api/attendance/today", headers=headers)
    assert att_today.status_code == 200

    # 3. Leave balances & apply
    bal_res = client.get("/api/leave/balances", headers=headers)
    assert bal_res.status_code == 200
    bals = bal_res.get_json()["balances"]
    assert "Casual Leave" in bals or "Sick Leave" in bals

    # 4. Submit timesheet
    ts_res = client.post("/api/timesheets/submit", headers=headers, json={
        "weekStartDate": "2026-10-12",
        "projectName": "Enterprise HRMS Platform",
        "hoursBreakdown": {"mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
        "totalHours": 40,
        "notes": "Delivered complete RBAC authentication and employee self-service."
    })
    assert ts_res.status_code in {200, 201}

    # 5. Check my timesheets
    my_ts = client.get("/api/timesheets/my", headers=headers)
    assert my_ts.status_code == 200
    assert len(my_ts.get_json()) >= 1

    # 6. Check my payslips
    my_payslips = client.get("/api/payslips/my", headers=headers)
    assert my_payslips.status_code == 200

    # 7. Check notifications
    notifs = client.get("/api/notifications", headers=headers)
    assert notifs.status_code == 200

def test_05_recruiter_hrms_permissions(client):
    token, auth_data = login(client, "recruiter@kyktechnologies.com", "Recruiter@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Recruiter profile & HRMS tabs
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] == "recruiter"
    assert "recruitment" in me["tabs"]
    assert "onboarding" in me["tabs"]
    assert "my_attendance" in me["tabs"]
    assert "my_leaves" in me["tabs"]
    assert "my_payslips" in me["tabs"]
    assert "payroll" not in me["tabs"]
    assert "audit_log" not in me["tabs"]

    # 2. Recruiter can access recruitment & onboarding
    onb_res = client.get("/api/onboarding/tasks", headers=headers)
    assert onb_res.status_code == 200

    # 3. Recruiter cannot perform admin/HR-only actions like payroll runs or creating branches
    payroll_res = client.post("/api/payroll/runs", headers=headers, json={"month": "2026-10"})
    assert payroll_res.status_code == 403

    branch_res = client.post("/api/admin/branches", headers=headers, json={"name": "Test", "city": "Test"})
    assert branch_res.status_code == 403

def test_06_content_manager_hrms_permissions(client):
    token, auth_data = login(client, "content.manager@kyktechnologies.com", "Content@12345")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify Content Manager profile & HRMS tabs
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me = me_res.get_json()["admin"]
    assert me["role"] == "content_manager"
    assert "my_attendance" in me["tabs"]
    assert "my_leaves" in me["tabs"]
    assert "my_payslips" in me["tabs"]
    assert "payroll" not in me["tabs"]
    assert "team" not in me["tabs"]

    # 2. Content Manager can access self-service
    att_today = client.get("/api/attendance/today", headers=headers)
    assert att_today.status_code == 200

    # 3. Content Manager cannot manage team or payroll
    mgr_res = client.get("/api/manager/team", headers=headers)
    assert mgr_res.status_code == 403

def test_07_client_and_viewer_hrms_access_denied(client):
    # Test Client
    client_token, _ = login(client, "client@kyktechnologies.com", "Client@12345")
    c_headers = {"Authorization": f"Bearer {client_token}"}

    c_me_res = client.get("/api/auth/me", headers=c_headers)
    assert c_me_res.status_code == 200
    c_me = c_me_res.get_json()["admin"]
    assert c_me["role"] == "client"
    # Client has NO HRMS tabs
    hrms_tabs = {"my_attendance", "attendance", "payroll", "leave_mgmt", "my_leaves", "my_payslips", "timesheets", "employees"}
    assert not any(t in c_me["tabs"] for t in hrms_tabs)

    # Client cannot access HRMS endpoints (403 forbidden)
    att_res = client.get("/api/attendance/today", headers=c_headers)
    assert att_res.status_code == 403

    leave_res = client.get("/api/leave/balances", headers=c_headers)
    assert leave_res.status_code == 403

    payslip_res = client.get("/api/payslips/my", headers=c_headers)
    assert payslip_res.status_code == 403

    emp_res = client.get("/api/admin/employees", headers=c_headers)
    assert emp_res.status_code == 403

    # Test Viewer
    viewer_token, _ = login(client, "viewer@kyktechnologies.com", "Viewer@12345")
    v_headers = {"Authorization": f"Bearer {viewer_token}"}

    v_me_res = client.get("/api/auth/me", headers=v_headers)
    assert v_me_res.status_code == 200
    v_me = v_me_res.get_json()["admin"]
    assert v_me["role"] == "viewer"
    assert not any(t in v_me["tabs"] for t in hrms_tabs)

    # Viewer cannot access HRMS endpoints
    v_att = client.get("/api/attendance/today", headers=v_headers)
    assert v_att.status_code == 403

    v_emp = client.get("/api/admin/employees", headers=v_headers)
    assert v_emp.status_code == 403

    # Ensure static HTML pages for client, viewer, and general user do not expose any HRMS portal links/buttons
    for page in ["client-portal.html", "viewer-dashboard.html", "user-dashboard.html"]:
        res = client.get(f"/{page}")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "/hrms-portal.html" not in html
        assert "HRMS Portal" not in html

if __name__ == "__main__":
    pytest.main(["-v", __file__])
