import time
import pytest
from app import app
import db

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_db_read_nanosecond_speed():
    """Verify that database reads are served from in-memory cache in sub-millisecond speed."""
    # First call warms cache
    db.read("jobs")

    # Measure 50 consecutive reads
    start = time.perf_counter()
    for _ in range(50):
        jobs = db.read("jobs")
    elapsed = time.perf_counter() - start
    avg_seconds = elapsed / 50.0

    print(f"\nAverage db.read('jobs') time: {avg_seconds * 1_000_000:.2f} microseconds ({avg_seconds * 1_000_000_000:.0f} nanoseconds)")
    # Must be less than 1 millisecond (1,000 microseconds)
    assert avg_seconds < 0.001, f"Expected < 1ms, got {avg_seconds * 1000:.3f}ms"

def test_db_find_nanosecond_speed():
    """Verify that db.find executes in microseconds / nanoseconds."""
    # Warm
    db.read("admins")
    admins = db.read("admins")
    if admins:
        admin_id = admins[0]["id"]
        start = time.perf_counter()
        for _ in range(50):
            a = db.find("admins", admin_id)
        elapsed = time.perf_counter() - start
        avg_seconds = elapsed / 50.0
        print(f"\nAverage db.find('admins') time: {avg_seconds * 1_000_000:.2f} microseconds ({avg_seconds * 1_000_000_000:.0f} nanoseconds)")
        assert avg_seconds < 0.0005, f"Expected < 0.5ms, got {avg_seconds * 1000:.3f}ms"

def test_session_validation_speed():
    """Verify session JTI lookups execute in sub-millisecond memory speed."""
    test_jti = "perf-test-jti-12345"
    db.create_session("admin", 1, test_jti, 5, ip="127.0.0.1", ua="pytest", exp=int(time.time()) + 3600)

    try:
        start = time.perf_counter()
        for _ in range(50):
            s = db.get_session_by_jti(test_jti)
            assert s is not None
        elapsed = time.perf_counter() - start
        avg_seconds = elapsed / 50.0
        print(f"\nAverage get_session_by_jti time: {avg_seconds * 1_000_000:.2f} microseconds ({avg_seconds * 1_000_000_000:.0f} nanoseconds)")
        assert avg_seconds < 0.0005, f"Expected < 0.5ms, got {avg_seconds * 1000:.3f}ms"
    finally:
        db.revoke_session(test_jti)

def test_gzip_compression_on_static_and_json(client):
    """Verify that GZIP compression compresses responses significantly."""
    # Request large JS file with gzip Accept-Encoding
    res_gzip = client.get("/js/dash-common.js", headers={"Accept-Encoding": "gzip"})
    assert res_gzip.status_code == 200
    assert res_gzip.headers.get("Content-Encoding") == "gzip"
    compressed_len = int(res_gzip.headers.get("Content-Length", 0))

    # Request without gzip
    res_raw = client.get("/js/dash-common.js")
    assert res_raw.status_code == 200
    raw_len = len(res_raw.data)

    print(f"\nStatic JS compression: raw={raw_len} bytes -> compressed={compressed_len} bytes ({((raw_len - compressed_len) / raw_len) * 100:.1f}% reduction)")
    assert compressed_len < raw_len * 0.40  # Over 60% compression!

def test_100_concurrent_members_speed():
    """Simulate 100 concurrent members hitting the website simultaneously."""
    import concurrent.futures

    def member_journey(user_id):
        t0 = time.perf_counter()
        with app.test_client() as user_client:
            # 1. Fetch home page
            r1 = user_client.get("/")
            assert r1.status_code == 200
            # 2. Fetch public insights API
            r2 = user_client.get("/api/insights")
            assert r2.status_code == 200
            # 3. Fetch stats API
            r3 = user_client.get("/api/stats")
            assert r3.status_code == 200
            # 4. Direct in-memory DB read
            jobs = db.read("jobs")
            assert isinstance(jobs, list)
        return time.perf_counter() - t0

    # Pre-warm cached routes and collections so concurrent surge runs purely in memory
    with app.test_client() as warmup:
        warmup.get("/")
        warmup.get("/api/insights")
        warmup.get("/api/stats")
        db.read("jobs")

    start_total = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(member_journey, i) for i in range(100)]
        durations = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_time = time.perf_counter() - start_total
    avg_duration = sum(durations) / len(durations)

    print(f"\n[OK] 100 CONCURRENT USERS FINISHED 400 OPERATIONS IN: {total_time:.3f} seconds total!")
    print(f"[OK] Average round-trip time per member: {avg_duration * 1000:.2f} ms")
    assert total_time < 3.0

