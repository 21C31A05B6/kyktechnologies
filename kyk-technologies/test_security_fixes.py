from app import is_account_active, sanitize_redirect_target, resolve_upload_dir


def test_account_status_blocks_disabled_users():
    assert is_account_active({"status": "active"}) is True
    assert is_account_active({"status": "inactive"}) is False
    assert is_account_active({"status": "suspended"}) is False
    assert is_account_active({"status": "terminated"}) is False


def test_redirect_target_is_same_origin_only():
    assert sanitize_redirect_target("/user-dashboard.html") == "/user-dashboard.html"
    assert sanitize_redirect_target("/careers.html") == "/careers.html"
    assert sanitize_redirect_target("https://evil.example") is None
    assert sanitize_redirect_target("//evil.example") is None
    assert sanitize_redirect_target("javascript:alert(1)") is None


def test_upload_dir_resolves_from_env_or_fallback(monkeypatch, tmp_path):
    from app import resolve_upload_dir

    custom_root = tmp_path / "custom-uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(custom_root))
    assert resolve_upload_dir("UPLOAD_DIR", str(tmp_path / "fallback")) == str(custom_root)

    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    fallback_root = tmp_path / "fallback"
    assert resolve_upload_dir("UPLOAD_DIR", str(fallback_root)) == str(fallback_root)


def test_audit_log_alias_is_supported():
    from db_sql import read

    rows = read("audit_logs")
    assert isinstance(rows, list)
