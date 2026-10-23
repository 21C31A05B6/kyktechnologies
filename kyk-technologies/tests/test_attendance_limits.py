import pytest
from app import app, db, _today_key, _now_local


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


def test_attendance_one_punch_per_day_and_exact_duration(client):
    token, admin = login(client, "employee@kyktechnologies.com", "Emp@12345")
    headers = {"Authorization": f"Bearer {token}"}
    date_key = _today_key()

    # Clean existing attendance for employee so test starts in completely clean state
    all_att = [r for r in db.read("attendance") if r.get("adminId") != admin["id"]]
    db.write("attendance", all_att)

    # 1. Initially today's attendance has not been punched
    today_res = client.get("/api/attendance/today", headers=headers)
    assert today_res.status_code == 200
    today_data = today_res.get_json()
    assert today_data["canCheckIn"] is True
    assert today_data["isCompleted"] is False
    assert today_data["checkIn"] is None

    # 2. First check-in of the day succeeds
    in_res = client.post("/api/attendance/checkin", headers=headers)
    assert in_res.status_code == 201
    in_data = in_res.get_json()
    assert in_data["date"] == date_key
    assert in_data["checkIn"] is not None
    assert in_data["checkOut"] is None

    # 3. Attempting a second check-in while checked in MUST fail (400)
    in_again_res = client.post("/api/attendance/checkin", headers=headers)
    assert in_again_res.status_code == 400
    assert "already checked in" in in_again_res.get_json()["error"].lower()

    # 4. Check status while checked in
    today_mid = client.get("/api/attendance/today", headers=headers)
    assert today_mid.status_code == 200
    mid_data = today_mid.get_json()
    assert mid_data["canCheckIn"] is False
    assert mid_data["canCheckOut"] is True
    assert mid_data["isCompleted"] is False

    # 5. Check out of today's attendance
    out_res = client.post("/api/attendance/checkout", headers=headers)
    assert out_res.status_code == 200
    out_data = out_res.get_json()
    assert out_data["checkOut"] is not None
    assert out_data["workedSeconds"] is not None
    assert "workedFormatted" in out_data
    assert "h" in out_data["workedFormatted"] and "s" in out_data["workedFormatted"]

    # 6. Attempting to check in AGAIN on the same day MUST fail (400) - 1 day for 1 time!
    in_third_res = client.post("/api/attendance/checkin", headers=headers)
    assert in_third_res.status_code == 400
    error_msg = in_third_res.get_json()["error"].lower()
    assert "already checked in and checked out" in error_msg or "tomorrow" in error_msg or "1 check-in" in error_msg

    # 7. Attempting to check out AGAIN on the same day MUST fail (400)
    out_again_res = client.post("/api/attendance/checkout", headers=headers)
    assert out_again_res.status_code == 400
    assert "already checked out" in out_again_res.get_json()["error"].lower()

    # 8. Final today status verification
    final_res = client.get("/api/attendance/today", headers=headers)
    assert final_res.status_code == 200
    final_data = final_res.get_json()
    assert final_data["canCheckIn"] is False
    assert final_data["canCheckOut"] is False
    assert final_data["isCompleted"] is True
    assert final_data["checkIn"] is not None
    assert final_data["checkOut"] is not None
    assert final_data["timeZone"] == "Asia/Kolkata"
