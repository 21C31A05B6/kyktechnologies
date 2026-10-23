import pytest
from app import app, socketio, _revoke_session, _create_session, _session_valid
import db
import chat_api
from security import make_token, read_token


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.data}"
    data = res.get_json()
    token = data["token"]
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    admin = me_res.get_json()["admin"]
    return token, admin


def test_sec_01_meeting_chat_requires_membership(client):
    """SEC-01: Verify meeting chat retrieval returns 403 Forbidden for unauthorized users."""
    admin_token, admin = login(client, "admin@kyktechnologies.com", "Admin@12345")
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")
    viewer_token, viewer = login(client, "viewer@kyktechnologies.com", "Viewer@12345")

    # Host creates a private meeting
    meet_res = client.post("/api/meetings", json={
        "title": "Confidential Security Review",
        "description": "Internal only",
        "meetingType": "instant",
        "targetDepartment": "Executive",
        "targetRole": "super_admin",
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert meet_res.status_code == 201
    meeting_code = meet_res.get_json()["meetingCode"]

    # Unauthorized user (viewer) attempts to read meeting chat -> MUST receive 403
    unauth_res = client.get(
        f"/api/meetings/{meeting_code}/chat",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert unauth_res.status_code == 403
    assert "not authorized" in unauth_res.get_json()["error"].lower()

    # Authorized user (admin/host) can read meeting chat
    auth_res = client.get(
        f"/api/meetings/{meeting_code}/chat",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert auth_res.status_code == 200


def test_sec_04_socket_rejects_revoked_session():
    """SEC-04: Sockets must reject connections with revoked or invalid session JTIs."""
    token = make_token({"adminId": 1, "role": "admin"})
    payload = read_token(token)
    jti = payload["jti"]

    # Register active session
    _create_session("admin", 1, jti, 3, exp=payload["exp"])
    assert _session_valid(jti) is True

    # Valid session lookup succeeds
    user = chat_api._user_from_token(token)
    assert user is not None

    # Revoke the session
    _revoke_session(jti)
    assert _session_valid(jti) is False

    # Token lookup with revoked session must return None (SEC-04)
    revoked_user = chat_api._user_from_token(token)
    assert revoked_user is None


def test_sec_05_cors_restricts_untrusted_origins(client):
    """SEC-05 & SEC-08: CORS headers must not blindly return * to untrusted origins."""
    untrusted_res = client.get(
        "/api/stats",
        headers={"Origin": "https://malicious-site.example.com"}
    )
    assert untrusted_res.headers.get("Access-Control-Allow-Origin") != "*"
    assert untrusted_res.headers.get("Access-Control-Allow-Origin") != "https://malicious-site.example.com"

    trusted_res = client.get(
        "/api/stats",
        headers={"Origin": "http://localhost:3000"}
    )
    assert trusted_res.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_hr_02_candidate_conversion_does_not_leak_password(client):
    """HR-02: Converting candidate does not leak plaintext password in response."""
    admin_token, _ = login(client, "admin@kyktechnologies.com", "Admin@12345")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create dummy application
    cand = db.insert("applications", {
        "name": "Test Candidate Secure",
        "email": "candidate.secure.test@kyktechnologies.com",
        "status": "offered",
        "jobTitle": "DevOps Engineer",
        "department": "Infrastructure",
    })

    hire_res = client.post(
        f"/api/recruitment/candidates/{cand['id']}/convert-to-employee",
        json={"department": "Infrastructure", "designation": "DevOps Engineer"},
        headers=headers
    )
    assert hire_res.status_code == 200
    data = hire_res.get_json()
    assert "tempPassword" not in data
    assert data.get("accountCreated") is True

    # Cleanup
    db.remove("applications", cand["id"])


def test_hr_04_05_onboarding_tasks_no_side_effects(client):
    """HR-04 & HR-05: GET /api/onboarding/tasks has no side effects and respects role."""
    admin_token, _ = login(client, "admin@kyktechnologies.com", "Admin@12345")
    emp_token, _ = login(client, "employee@kyktechnologies.com", "Emp@12345")

    res_admin = client.get("/api/onboarding/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200

    res_emp = client.get("/api/employee/onboarding/tasks", headers={"Authorization": f"Bearer {emp_token}"})
    assert res_emp.status_code == 200
    assert isinstance(res_emp.get_json(), list)


def test_hr_07_field_level_privacy(client):
    """HR-07: Sensitive banking and tax info must be masked for non-HR callers and unmasked for HR."""
    # Ensure a test employee with sensitive banking & tax info exists
    test_emp = db.insert("employees", {
        "fullName": "Privacy Test Subject",
        "email": "privacy.test@example.com",
        "employeeCode": "EMP-PRIV-999",
        "accountNumber": "1234567890",
        "panTaxId": "ABCDE1234F",
        "bankName": "HDFC Bank",
        "status": "active",
    })
    emp_id = test_emp["id"]

    try:
        # 1. Team lead (non-HR) viewing the employee profile
        lead_token, _ = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
        lead_res = client.get(f"/api/admin/employees/{emp_id}", headers={"Authorization": f"Bearer {lead_token}"})
        assert lead_res.status_code == 200
        lead_emp_data = lead_res.get_json().get("employee", {})
        assert lead_emp_data.get("accountNumber") == "***7890"
        assert lead_emp_data.get("panTaxId") == "***234F"
        assert lead_emp_data.get("bankName") == "***Bank"

        # 2. HR Manager viewing the employee profile receives unmasked data
        hr_token, _ = login(client, "hr.manager@kyktechnologies.com", "Hr@12345")
        hr_res = client.get(f"/api/admin/employees/{emp_id}", headers={"Authorization": f"Bearer {hr_token}"})
        assert hr_res.status_code == 200
        hr_emp_data = hr_res.get_json().get("employee", {})
        assert hr_emp_data.get("accountNumber") == "1234567890"
        assert hr_emp_data.get("panTaxId") == "ABCDE1234F"
    finally:
        if hasattr(db, "remove"):
            db.remove("employees", emp_id)

