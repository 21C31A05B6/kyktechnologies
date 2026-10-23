"""tests/test_chat_meetings.py — Comprehensive Test Suite for KYK Technologies Enterprise Chat & Meeting Platform.
Tests:
- 1:1 direct messaging
- Group channels and membership
- Role-based announcement channels (Admin/HR allowed, Employee rejected with 403)
- Unauthorized access / IDOR protection (non-member rejected with 403)
- Message editing and deletion authorization
- Read receipts and unread tracking
- Reactions and message pinning
- WebRTC meeting lifecycle (instant, scheduling, RSVP, host authorization)
"""

import pytest
import json
from datetime import datetime, timedelta, timezone

# Ensure database URL is loaded before importing app
import db
from app import app
from models import ChatConversation, ChatMessage, Meeting

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
    # Fetch authenticated user profile
    headers = {"Authorization": f"Bearer {data['token']}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200, f"/api/auth/me failed for {email}: {me_res.get_data(as_text=True)}"
    user_info = me_res.get_json()["admin"]
    return data["token"], user_info

def test_01_direct_message_lifecycle(client):
    """Test 1:1 direct messaging between Employee and Team Lead."""
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")
    lead_token, lead = login(client, "team.lead@kyktechnologies.com", "Lead@12345")

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    lead_headers = {"Authorization": f"Bearer {lead_token}"}

    emp_id = emp["id"]
    lead_id = lead["id"]

    # 1. Employee starts a 1:1 conversation with Team Lead
    create_res = client.post("/api/chat/conversations", json={
        "type": "direct",
        "targetUserId": lead_id
    }, headers=emp_headers)
    assert create_res.status_code in {200, 201}
    conv_data = create_res.get_json()
    conv_id = conv_data["id"]
    assert conv_data["type"] == "direct"

    # 2. Employee sends a text message
    msg_res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
        "content": "Hello Team Lead, this is a test direct message."
    }, headers=emp_headers)
    assert msg_res.status_code == 201
    msg_data = msg_res.get_json()
    msg_id = msg_data["id"]
    assert msg_data["content"] == "Hello Team Lead, this is a test direct message."

    # 3. Team Lead fetches conversation messages
    list_res = client.get(f"/api/chat/conversations/{conv_id}/messages", headers=lead_headers)
    assert list_res.status_code == 200
    res_data = list_res.get_json()
    msgs = res_data if isinstance(res_data, list) else res_data.get("messages", [])
    assert any(m["id"] == msg_id for m in msgs)

    # 4. Team Lead sends a reply
    reply_res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
        "content": "Received loud and clear, Employee!",
        "replyToId": msg_id
    }, headers=lead_headers)
    assert reply_res.status_code == 201
    reply_data = reply_res.get_json()
    assert reply_data.get("replyToId") == msg_id or reply_data.get("reply_to_id") == msg_id

    # 5. Team Lead marks conversation as read
    read_res = client.post(f"/api/chat/conversations/{conv_id}/read", headers=lead_headers)
    assert read_res.status_code == 200
    assert read_res.get_json().get("ok") is True or read_res.get_json().get("success") is True

def test_02_group_messaging_and_management(client):
    """Test group creation, member management, and communication."""
    lead_token, lead = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")

    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    emp_id = emp["id"]

    # 1. Team lead creates a project group
    create_group_res = client.post("/api/chat/conversations", json={
        "type": "group",
        "title": "Project Alpha Sprint",
        "description": "Sprint planning and daily standups"
    }, headers=lead_headers)
    assert create_group_res.status_code == 201
    group_id = create_group_res.get_json()["id"]

    # 2. Team lead adds employee to the group
    add_res = client.post(f"/api/chat/conversations/{group_id}/members", json={
        "userId": emp_id,
        "role": "member"
    }, headers=lead_headers)
    assert add_res.status_code == 200
    assert add_res.get_json().get("success") is True or add_res.get_json().get("ok") is True

    # 3. Employee sends message to the group
    emp_msg_res = client.post(f"/api/chat/conversations/{group_id}/messages", json={
        "content": "Employee joined Project Alpha Sprint group!"
    }, headers=emp_headers)
    assert emp_msg_res.status_code == 201
    assert emp_msg_res.get_json()["content"] == "Employee joined Project Alpha Sprint group!"

def test_03_role_based_channel_announcements(client):
    """Test that Admin/HR can post to #announcements but regular Employee is rejected with 403."""
    admin_token, _ = login(client, "admin@kyktechnologies.com", "Admin@12345")
    emp_token, _ = login(client, "employee@kyktechnologies.com", "Emp@12345")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 1. Admin lists conversations to locate #announcements channel
    convs_res = client.get("/api/chat/conversations", headers=admin_headers)
    assert convs_res.status_code == 200
    convs = convs_res.get_json()
    ann_conv = next((c for c in convs if c.get("isAnnouncement") or c.get("is_announcement") or c.get("type") == "announcement"), None)
    assert ann_conv is not None, "System #announcements channel not found"
    ann_id = ann_conv["id"]

    # 2. Admin posts an announcement -> should succeed (201)
    admin_post_res = client.post(f"/api/chat/conversations/{ann_id}/messages", json={
        "content": "All-hands company announcement: Q4 goals achieved!"
    }, headers=admin_headers)
    assert admin_post_res.status_code == 201

    # 3. Employee attempts to post to #announcements -> must be rejected (403)
    emp_post_res = client.post(f"/api/chat/conversations/{ann_id}/messages", json={
        "content": "Unauthorized employee announcement attempt"
    }, headers=emp_headers)
    assert emp_post_res.status_code == 403
    err_msg = emp_post_res.get_json().get("error", "")
    assert "announcement" in err_msg.lower() or "permission" in err_msg.lower()

def test_04_unauthorized_idor_prevention(client):
    """Test that a non-member cannot read or post to a private conversation."""
    hr_token, hr = login(client, "hr.manager@kyktechnologies.com", "Hr@12345")
    admin_token, admin = login(client, "admin@kyktechnologies.com", "Admin@12345")
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")

    hr_headers = {"Authorization": f"Bearer {hr_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 1. HR Manager creates private 1:1 with Admin
    admin_id = admin["id"]
    priv_conv_res = client.post("/api/chat/conversations", json={
        "type": "direct",
        "targetUserId": admin_id
    }, headers=hr_headers)
    assert priv_conv_res.status_code in {200, 201}
    priv_conv_id = priv_conv_res.get_json()["id"]

    # 2. HR Manager posts confidential message
    client.post(f"/api/chat/conversations/{priv_conv_id}/messages", json={
        "content": "Confidential compensation review discussion."
    }, headers=hr_headers)

    # 3. Unauthorized Employee tries to view messages in HR-Admin conversation -> 403 Forbidden
    unauth_view_res = client.get(f"/api/chat/conversations/{priv_conv_id}/messages", headers=emp_headers)
    assert unauth_view_res.status_code == 403
    assert "denied" in unauth_view_res.get_json().get("error", "").lower() or "member" in unauth_view_res.get_json().get("error", "").lower()

    # 4. Unauthorized Employee tries to post to HR-Admin conversation -> 403 Forbidden
    unauth_post_res = client.post(f"/api/chat/conversations/{priv_conv_id}/messages", json={
        "content": "Spying attempt"
    }, headers=emp_headers)
    assert unauth_post_res.status_code == 403

def test_05_message_edit_delete_permissions(client):
    """Test editing and soft-deleting messages with strict authorization."""
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")
    lead_token, lead = login(client, "team.lead@kyktechnologies.com", "Lead@12345")

    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    lead_headers = {"Authorization": f"Bearer {lead_token}"}

    # Team Lead creates group conversation
    conv_res = client.post("/api/chat/conversations", json={
        "type": "group",
        "title": "Test Edit Channel"
    }, headers=lead_headers)
    assert conv_res.status_code == 201
    conv_id = conv_res.get_json()["id"]

    # Team Lead adds employee to group
    client.post(f"/api/chat/conversations/{conv_id}/members", json={
        "userId": emp["id"],
        "role": "member"
    }, headers=lead_headers)

    # Employee posts message
    msg_res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
        "content": "Original message content"
    }, headers=emp_headers)
    assert msg_res.status_code == 201
    msg_id = msg_res.get_json()["id"]

    # Team Lead attempts to edit Employee's message -> 403
    lead_edit_res = client.put(f"/api/chat/messages/{msg_id}", json={
        "content": "Tampered content"
    }, headers=lead_headers)
    assert lead_edit_res.status_code == 403

    # Employee edits own message -> 200 OK
    emp_edit_res = client.put(f"/api/chat/messages/{msg_id}", json={
        "content": "Updated message content by author"
    }, headers=emp_headers)
    assert emp_edit_res.status_code == 200
    assert emp_edit_res.get_json()["content"] == "Updated message content by author"
    assert emp_edit_res.get_json().get("isEdited") is True or emp_edit_res.get_json().get("is_edited") is True

    # Employee soft deletes message -> 200 OK
    del_res = client.delete(f"/api/chat/messages/{msg_id}", headers=emp_headers)
    assert del_res.status_code == 200
    assert del_res.get_json().get("isDeleted") is True or del_res.get_json().get("is_deleted") is True
    assert "deleted" in del_res.get_json()["content"].lower()

def test_06_reactions_and_pinning(client):
    """Test emoji reactions and message pinning."""
    emp_token, emp = login(client, "employee@kyktechnologies.com", "Emp@12345")
    lead_token, lead = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    lead_headers = {"Authorization": f"Bearer {lead_token}"}

    conv_res = client.post("/api/chat/conversations", json={
        "type": "group",
        "title": "Reaction Lab"
    }, headers=lead_headers)
    assert conv_res.status_code == 201
    conv_id = conv_res.get_json()["id"]

    # Team Lead adds employee to group
    client.post(f"/api/chat/conversations/{conv_id}/members", json={
        "userId": emp["id"],
        "role": "member"
    }, headers=lead_headers)

    msg_res = client.post(f"/api/chat/conversations/{conv_id}/messages", json={
        "content": "Great work on the release today! 🎉"
    }, headers=lead_headers)
    assert msg_res.status_code == 201
    msg_id = msg_res.get_json()["id"]

    # Add reaction
    react_res = client.post(f"/api/chat/messages/{msg_id}/reactions", json={
        "emoji": "🚀"
    }, headers=emp_headers)
    assert react_res.status_code == 200
    reactions = react_res.get_json()["reactions"]
    assert any(r.get("emoji") == "🚀" for r in reactions)

    # Pin message by owner (Team Lead)
    pin_res = client.post(f"/api/chat/messages/{msg_id}/pin", headers=lead_headers)
    assert pin_res.status_code == 200
    assert pin_res.get_json().get("isPinned") is True or pin_res.get_json().get("is_pinned") is True

    # Unpin message
    unpin_res = client.post(f"/api/chat/messages/{msg_id}/pin", headers=lead_headers)
    assert unpin_res.status_code == 200
    assert unpin_res.get_json().get("isPinned") is False or unpin_res.get_json().get("is_pinned") is False

def test_07_meeting_lifecycle_and_rsvp(client):
    """Test WebRTC meeting creation, scheduling, RSVP and completion."""
    lead_token, _ = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
    emp_token, _ = login(client, "employee@kyktechnologies.com", "Emp@12345")

    lead_headers = {"Authorization": f"Bearer {lead_token}"}
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 1. Team lead starts an instant meeting
    inst_res = client.post("/api/meetings/instant", json={
        "title": "Ad-hoc Architecture Sync"
    }, headers=lead_headers)
    assert inst_res.status_code == 201
    inst_data = inst_res.get_json()
    inst_code = inst_data.get("meetingCode") or inst_data.get("meeting_code")
    assert inst_code is not None
    assert inst_data["status"] == "live"

    # 2. Team lead schedules a future meeting
    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(days=1)).isoformat()
    end_time = (now + timedelta(days=1, hours=1)).isoformat()

    sched_res = client.post("/api/meetings/schedule", json={
        "title": "Weekly Engineering Retrospective",
        "description": "Sprint review and roadmap planning",
        "scheduledStart": start_time,
        "scheduledEnd": end_time
    }, headers=lead_headers)
    assert sched_res.status_code == 201
    sched_data = sched_res.get_json()
    sched_code = sched_data.get("meetingCode") or sched_data.get("meeting_code")
    assert sched_code is not None
    assert sched_data["status"] == "scheduled"

    # 3. Employee RSVPs 'accepted'
    rsvp_res = client.post(f"/api/meetings/{sched_code}/rsvp", json={
        "status": "accepted"
    }, headers=emp_headers)
    assert rsvp_res.status_code == 200
    assert rsvp_res.get_json().get("success") is True or rsvp_res.get_json().get("ok") is True

    # 4. Fetch meeting list
    list_res = client.get("/api/meetings", headers=emp_headers)
    assert list_res.status_code == 200
    meetings = list_res.get_json()
    assert any((m.get("meetingCode") == sched_code or m.get("meeting_code") == sched_code) for m in meetings)

    # 5. Non-host Employee attempts to end the instant meeting -> 403 Forbidden
    unauth_end = client.post(f"/api/meetings/{inst_code}/end", headers=emp_headers)
    assert unauth_end.status_code == 403

    # 6. Host Team Lead ends the instant meeting -> 200 OK
    auth_end = client.post(f"/api/meetings/{inst_code}/end", headers=lead_headers)
    assert auth_end.status_code == 200
    assert auth_end.get_json().get("status") == "completed" or auth_end.get_json().get("ok") is True
