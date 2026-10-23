import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_enterprise_security_headers_present(client):
    """Verify that modern enterprise defense-in-depth headers are sent on all responses."""
    res = client.get("/")
    assert res.status_code == 200

    # 1. Anti-Clickjacking
    assert res.headers.get("X-Frame-Options") == "DENY"

    # 2. Anti-MIME type sniffing
    assert res.headers.get("X-Content-Type-Options") == "nosniff"

    # 3. Content Security Policy
    csp = res.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp

    # 4. Strict Transport Security (HSTS)
    assert "max-age=31536000" in res.headers.get("Strict-Transport-Security", "")

    # 5. Referrer Policy & Permissions Policy
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in res.headers.get("Permissions-Policy", "")

def test_waf_blocks_malicious_exploits(client):
    """Verify Web Application Firewall (WAF) blocks path traversal and injection probes."""
    app.config["TESTING_FIREWALL"] = True
    try:
        # Path traversal probe
        res1 = client.get("/../../etc/passwd")
        assert res1.status_code in (403, 404)

        # SQL injection / script injection probe in query string
        res2 = client.get("/api/insights?q=union+select+1,2,3")
        assert res2.status_code == 403

        # Script probe in query string
        res3 = client.get("/api/stats?x=<script>alert(1)</script>")
        assert res3.status_code == 403
    finally:
        app.config["TESTING_FIREWALL"] = False

def test_brute_force_account_lockout(client):
    """Verify that 5 consecutive failed logins lock the account temporarily."""
    app.config["TESTING_LOCKOUT"] = True
    try:
        # 5 failed login attempts
        for _ in range(5):
            r = client.post("/api/auth/login", json={"email": "victim@example.com", "password": "WrongPassword!999"})
            assert r.status_code == 401

        # 6th attempt must be locked out with 429
        r_locked = client.post("/api/auth/login", json={"email": "victim@example.com", "password": "WrongPassword!999"})
        assert r_locked.status_code == 429
        data = r_locked.get_json()
        assert "temporarily locked" in data.get("error", "").lower()
    finally:
        app.config["TESTING_LOCKOUT"] = False
