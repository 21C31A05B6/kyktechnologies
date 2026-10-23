"""security.py — password hashing and signed tokens, standard library only.

Replaces bcryptjs + jsonwebtoken from the Node version:
  * hash_password / verify_password use PBKDF2-HMAC-SHA256.
  * make_token / read_token issue and verify a compact HMAC-signed token
    (same idea as a JWT: base64 payload + signature, with an expiry).

Bug fix (was: only read APP_SECRET, ignoring SECRET_KEY from README):
  Now reads SECRET_KEY first, falls back to APP_SECRET, then the dev
  placeholder. In production, set SECRET_KEY and never commit it.

Bug fix (was: 120_000 iterations, README claimed 260_000):
  Raised to 260_000 to match documentation and current NIST guidance.
  Existing stored hashes keep their own iteration count in the $…$ string,
  so old passwords still verify correctly — only newly hashed passwords use
  the higher count.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time

# ----------------------------------------------------------------------- key
# Priority: SECRET_KEY (documented in README) → APP_SECRET (legacy).
# In production, SECRET_KEY must be set to a long random string.
_raw_secret = (os.environ.get("SECRET_KEY") or os.environ.get("APP_SECRET") or "").strip()
_is_production = bool(
    os.environ.get("RENDER")
    or os.environ.get("KYK_PRODUCTION")
    or os.environ.get("FLASK_ENV") == "production"
    or os.environ.get("ENVIRONMENT") == "production"
    or os.environ.get("ENV") == "production"
)

if not _raw_secret:
    if _is_production:
        sys.exit(
            "FATAL: SECRET_KEY is not configured in production environment. "
            "Set SECRET_KEY to a cryptographically secure random value before starting.\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    # Ephemeral random key generated for local dev/test if not set: prevents predictable token forgery (SEC-09)
    _raw_secret = secrets.token_hex(32)
    print("NOTE: No SECRET_KEY configured; generated ephemeral random secret for development.")
elif _raw_secret in ("kyk-dev-secret-change-me", "changeme", "secret"):
    if _is_production:
        sys.exit(
            "FATAL: Insecure default SECRET_KEY detected in production environment. "
            "Set SECRET_KEY to a secure random value."
        )
    print("WARNING: Using known default SECRET_KEY in non-production.")

SECRET = _raw_secret
TOKEN_TTL = 60 * 60 * 8   # 8 hours
ITERATIONS = 260_000       # NIST SP 800-132 recommendation as of 2023


# ---------- passwords ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


# ---------- tokens ----------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    sig = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64(sig)


def make_token(payload: dict) -> str:
    """Issue a signed token.  A unique `jti` (session ID) is added so
    individual browser sessions can be tracked and revoked independently."""
    body = {
        **payload,
        "jti": secrets.token_hex(16),   # unique per browser session
        "exp": int(time.time()) + TOKEN_TTL,
    }
    payload_b64 = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def read_token(token: str):
    """Return the payload dict, or None if the token is invalid or expired."""
    if not token or "." not in token:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), sig):
        return None
    try:
        payload = json.loads(_unb64(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
