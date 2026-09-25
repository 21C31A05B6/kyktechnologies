"""seed_demo_users.py — creates one demo login per role for testing.

Run once after your first `python3 app.py` (so the admins table/DB exists):

    python3 seed_demo_users.py

By default every demo account gets its own random password, printed once.
To use the SAME password for all demo accounts instead (handy while
testing), set DEMO_PASSWORD before running:

    DEMO_PASSWORD=Test@12345 python3 seed_demo_users.py

Safe to re-run: any role that already has an account is skipped, so this
never overwrites a password you've already changed.
"""

import os
import secrets

import db
from security import hash_password

# role -> (email, display name). super_admin is intentionally excluded —
# it comes from the ADMIN_EMAIL / ADMIN_PASSWORD env vars in seed.py.
DEMO_USERS = {
    "hr_manager":      ("hr.manager@kyktechnologies.com",      "Demo HR Manager"),
    "recruiter":       ("recruiter@kyktechnologies.com",       "Demo Recruiter"),
    "content_manager": ("content.manager@kyktechnologies.com", "Demo Content Manager"),
    "team_lead":       ("team.lead@kyktechnologies.com",       "Demo Team Lead"),
    "employee":        ("employee@kyktechnologies.com",        "Demo Employee"),
    "viewer":          ("viewer@kyktechnologies.com",          "Demo Viewer"),
    "client":          ("client@kyktechnologies.com",          "Demo Client"),
}


def main():
    fixed_password = os.environ.get("DEMO_PASSWORD", "")
    existing_emails = {a.get("email", "").lower() for a in db.read("admins")}

    created = []
    skipped = []

    for role, (email, name) in DEMO_USERS.items():
        if email.lower() in existing_emails:
            skipped.append((role, email))
            continue
        password = fixed_password or secrets.token_urlsafe(10)
        db.insert("admins", {
            "email": email,
            "passwordHash": hash_password(password),
            "name": name,
            "role": role,
        })
        created.append((role, email, password))

    print("=" * 72)
    if created:
        print("  Demo credentials (save these now — passwords aren't stored anywhere):")
        print("-" * 72)
        for role, email, password in created:
            print(f"  {role:<17} {email:<32} {password}")
    else:
        print("  No new demo accounts created.")
    if skipped:
        print("-" * 72)
        print("  Already existed, left untouched:")
        for role, email in skipped:
            print(f"  {role:<17} {email}")
    print("=" * 72)
    print("  Sign in for each role at its own page:")
    print("    hr_manager      -> /hr-dashboard.html")
    print("    recruiter       -> /recruiter-dashboard.html")
    print("    content_manager -> /content-dashboard.html")
    print("    client          -> /client-portal.html")
    print("    team_lead       -> /team-lead-dashboard.html")
    print("    employee        -> /employee-dashboard.html (has attendance)")
    print("    viewer          -> /viewer-dashboard.html (read-only, no attendance)")
    print("=" * 72)


if __name__ == "__main__":
    main()
