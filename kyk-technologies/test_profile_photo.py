import io

from app import app
import db
from security import hash_password


def _create_admin(email, password, role="super_admin", name="Test Admin"):
    db.insert(
        "admins",
        {
            "name": name,
            "email": email,
            "passwordHash": hash_password(password),
            "role": role,
            "department": "Engineering",
            "designation": "Engineer",
            "phone": "+10000000000",
            "status": "active",
        },
    )


def test_employee_profile_photo_updates_and_admin_sees_it():
    client = app.test_client()
    admin_email = "profile-admin-123@example.com"
    admin_password = "AdminPass123"
    _create_admin(admin_email, admin_password, name="Profile Admin")

    admin_login = client.post("/api/auth/login", json={"email": admin_email, "password": admin_password})
    assert admin_login.status_code == 200, admin_login.get_data(as_text=True)
    admin_token = admin_login.get_json()["token"]

    employee_email = "employee-profile-photo@example.com"
    employee_password = "EmpPass123"
    _create_admin(employee_email, employee_password, role="employee", name="Employee Profile User")

    employee_login = client.post("/api/auth/login", json={"email": employee_email, "password": employee_password})
    assert employee_login.status_code == 200, employee_login.get_data(as_text=True)
    employee_token = employee_login.get_json()["token"]

    image_bytes = b"\x89PNG\r\n\x1a\n" + b"fake-image-data" + b"\n"
    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {employee_token}"},
        data={
            "name": "Updated Employee",
            "phone": "+15551234567",
            "password": "NewEmpPass123",
            "profilePhoto": (io.BytesIO(image_bytes), "avatar.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload.get("profilePhoto")

    me = client.get("/api/profile", headers={"Authorization": f"Bearer {employee_token}"})
    assert me.status_code == 200, me.get_data(as_text=True)
    me_data = me.get_json()
    assert me_data.get("profilePhoto")
    assert me_data.get("name") == "Updated Employee"

    admin_list = client.get("/api/admin/employees", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_list.status_code == 200, admin_list.get_data(as_text=True)
    rows = admin_list.get_json()
    employee_row = next((row for row in rows if row.get("email") == employee_email), None)
    assert employee_row is not None
    assert employee_row.get("profilePhoto")
