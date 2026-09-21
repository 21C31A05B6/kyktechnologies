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
# Priority: SECRET_KEY (documented in README) → APP_SECRET (legacy) → dev placeholder.
# In production, SECRET_KEY must be set to a long random string.
_raw_secret = (
    os.environ.get("SECRET_KEY")
    or os.environ.get("APP_SECRET")
    or "kyk-dev-secret-change-me"
)

if _raw_secret == "kyk-dev-secret-change-me":
    if os.environ.get("FLASK_ENV") == "production" or os.environ.get("KYK_PRODUCTION"):
        sys.exit(
            "FATAL: SECRET_KEY is not set. "
            "Set SECRET_KEY to a long random string before running in production.\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    print("WARNING: Using dev placeholder SECRET_KEY — not safe for production.")

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
    body = {**payload, "exp": int(time.time()) + TOKEN_TTL}
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
