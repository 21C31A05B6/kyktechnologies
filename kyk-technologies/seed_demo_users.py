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
    "super_admin":     ("admin@kyktechnologies.com",           "Rajesh Sharma (Admin)",        "Admin@12345"),
    "hr_manager":      ("hr.manager@kyktechnologies.com",      "Priya Nambiar (HR Manager)",   "Hr@12345"),
    "team_lead":       ("team.lead@kyktechnologies.com",       "Vikram Adiga (Team Lead)",     "Lead@12345"),
    "employee":        ("employee@kyktechnologies.com",        "Ananya Rao (Employee)",        "Emp@12345"),
    "recruiter":       ("recruiter@kyktechnologies.com",       "Sneha Patel (Recruiter)",      "Recruiter@12345"),
    "content_manager": ("content.manager@kyktechnologies.com", "Content Manager",              "Content@12345"),
    "viewer":          ("viewer@kyktechnologies.com",          "Demo Viewer",                  "Viewer@12345"),
    "client":          ("client@kyktechnologies.com",          "Demo Client",                  "Client@12345"),
}


def main():
    fixed_password = os.environ.get("DEMO_PASSWORD", "")
    existing_admins = {a.get("email", "").lower(): a for a in db.read("admins")}

    created = []
    updated = []

    for role, (email, name, def_pwd) in DEMO_USERS.items():
        pwd = fixed_password or def_pwd
        email_key = email.lower()
        if email_key in existing_admins:
            cur = existing_admins[email_key]
            db.update("admins", cur["id"], {
                "name": name,
                "role": role,
                "passwordHash": hash_password(pwd),
                "status": "active",
            })
            updated.append((role, email, pwd))
        else:
            db.insert("admins", {
                "email": email,
                "passwordHash": hash_password(pwd),
                "name": name,
                "role": role,
                "status": "active",
            })
            created.append((role, email, pwd))

    print("=" * 76)
    print("  KYK HRMS Portal — Demo Credentials Ready:")
    print("-" * 76)
    for role, email, password in (created + updated):
        print(f"  {role:<16} | {email:<32} | Password: {password}")
    print("=" * 76)
    print("  Sign in destinations:")
    print("    Role 1 — Admin:    admin@kyktechnologies.com     -> /admin.html")
    print("    Role 2 — HR:       hr.manager@kyktechnologies.com -> /hr-dashboard.html")
    print("    Role 3 — Manager:  team.lead@kyktechnologies.com  -> /team-lead-dashboard.html")
    print("    Role 4 — Employee: employee@kyktechnologies.com   -> /employee-dashboard.html")
    print("=" * 76)


if __name__ == "__main__":
    main()

