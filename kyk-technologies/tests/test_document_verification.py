"""Test suite for Document Management, 16 Official Document Types,
Manager & Admin Review (Approve / Reject), and Employee Re-upload Workflow.
"""

import io
import pytest
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

def test_document_types_endpoint(client):
    """Verify that all 16 requested official document types are exposed by the API."""
    token, _ = login(client, "employee@kyktechnologies.com", "Emp@12345")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/documents/types", headers=headers)
    assert res.status_code == 200
    types = res.get_json()
    type_names = [t["type"] for t in types]

    expected_16 = [
        "Employee Resume / CV",
        "Offer Letter",
        "Appointment Letter",
        "Employment Agreement",
        "Joining Letter",
        "Employee ID Proof",
        "Aadhaar Card",
        "PAN Card",
        "Passport",
        "Address Proof",
        "Educational Certificates",
        "Experience Certificates",
        "Relieving Letter",
        "Resignation Letter",
        "Salary Slips",
        "Bank Account Details Form"
    ]
    for expected in expected_16:
        assert expected in type_names, f"Missing document type: {expected}"

def test_document_upload_review_reject_reupload_approve(client):
    """End-to-End Test:
    1. Employee uploads Aadhaar Card.
    2. Manager checks and rejects with reason 'Blurry scan'.
    3. Employee sees rejected status and re-uploads document.
    4. Status resets to 'pending'.
    5. Manager reviews again and approves.
    6. Status becomes 'approved'.
    """
    emp_token, emp_data = login(client, "employee@kyktechnologies.com", "Emp@12345")
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    mgr_token, mgr_data = login(client, "team.lead@kyktechnologies.com", "Lead@12345")
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 1. Employee uploads Aadhaar Card file
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy aadhaar card content")
    upload_res = client.post(
        "/api/documents/upload",
        headers=emp_headers,
        data={
            "file": (dummy_pdf, "aadhaar_card_front_back.pdf"),
            "docType": "Aadhaar Card",
            "title": "Aadhaar Card - Front & Back",
            "category": "identity",
            "notes": "Original colored scan"
        },
        content_type="multipart/form-data"
    )
    assert upload_res.status_code == 201, upload_res.get_data(as_text=True)
    uploaded_doc = upload_res.get_json()
    doc_id = uploaded_doc["id"]
    assert uploaded_doc["status"] == "pending"
    assert uploaded_doc["docType"] == "Aadhaar Card"

    # 2. Manager checks Document Review list
    review_res = client.get("/api/documents/all?status=pending", headers=mgr_headers)
    assert review_res.status_code == 200
    pending_docs = review_res.get_json()
    assert any(d["id"] == doc_id for d in pending_docs)

    # 3. Manager rejects the document with feedback
    reject_reason = "Document scan is blurry and QR code is unreadable. Please re-upload a clear copy."
    reject_res = client.post(
        f"/api/documents/{doc_id}/reject",
        headers=mgr_headers,
        json={"reason": reject_reason}
    )
    assert reject_res.status_code == 200
    rej_data = reject_res.get_json()
    assert rej_data["status"] == "rejected"

    # 4. Employee checks My Documents
    my_docs_res = client.get("/api/documents/my", headers=emp_headers)
    assert my_docs_res.status_code == 200
    my_data = my_docs_res.get_json()
    assert my_data["stats"]["rejectedCount"] >= 1

    # Find Aadhaar card in the 16 checklist slots
    aadhaar_item = next(c for c in my_data["checklist"] if c["type"] == "Aadhaar Card")
    assert aadhaar_item["status"] == "rejected"
    assert aadhaar_item["isRejected"] is True
    assert aadhaar_item["rejectionReason"] == reject_reason

    # 5. Employee re-uploads corrected document
    corrected_pdf = io.BytesIO(b"%PDF-1.4 high resolution clear aadhaar copy")
    reupload_res = client.post(
        "/api/documents/upload",
        headers=emp_headers,
        data={
            "file": (corrected_pdf, "aadhaar_card_hd_clear.pdf"),
            "docId": str(doc_id),
            "docType": "Aadhaar Card",
            "title": "Aadhaar Card - High Resolution Clear Copy",
            "category": "identity",
            "notes": "Re-uploaded clear 300 DPI scan as requested."
        },
        content_type="multipart/form-data"
    )
    assert reupload_res.status_code == 201
    reuploaded_doc = reupload_res.get_json()
    assert reuploaded_doc["status"] == "pending", "Status must reset to pending on re-upload!"
    assert reuploaded_doc["rejectionReason"] is None, "Previous rejection reason must be cleared!"
    assert reuploaded_doc["version"] >= 2, "Document version must increment!"

    # 6. Manager approves the re-uploaded document
    approve_res = client.post(
        f"/api/documents/{doc_id}/approve",
        headers=mgr_headers,
        json={"notes": "Aadhaar is clear and fully legible. Approved."}
    )
    assert approve_res.status_code == 200
    assert approve_res.get_json()["status"] == "approved"

    # 7. Employee checks My Documents again and verifies status is Approved
    final_my_res = client.get("/api/documents/my", headers=emp_headers)
    assert final_my_res.status_code == 200
    final_data = final_my_res.get_json()
    final_aadhaar = next(c for c in final_data["checklist"] if c["type"] == "Aadhaar Card")
    assert final_aadhaar["status"] == "approved"
    assert final_aadhaar["isApproved"] is True
