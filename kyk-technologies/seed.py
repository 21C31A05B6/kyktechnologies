"""seed.py — populates initial demo data on first run.

Bug fix: admin credentials are no longer hard-coded.
  Set ADMIN_EMAIL + ADMIN_PASSWORD env vars before the first run.
  Falls back to printed-once random credentials when neither is set,
  so accidental public deployment with well-known credentials is prevented.
"""

import os
import secrets
import db
from security import hash_password

JOBS = [
    {
        "title": "Senior Full-Stack Engineer",
        "department": "Software & Web Services",
        "location": "Remote — Global",
        "type": "Full-time",
        "level": "Senior",
        "description": "Build and ship production SaaS features across our client platforms, from API design to polished UI.",
        "requirements": [
            "5+ years building web applications (Python, JavaScript, or similar)",
            "Comfort owning a feature from design to deployment",
            "Experience with cloud infrastructure (AWS, GCP, or Azure)",
        ],
        "active": True,
    },
    {
        "title": "AI Solutions Engineer",
        "department": "AI, AGI, ASI Applications",
        "location": "Hyderabad, IN / Remote",
        "type": "Full-time",
        "level": "Mid–Senior",
        "description": "Design and deploy applied AI systems — agents, automations, and integrations — for enterprise clients.",
        "requirements": [
            "Experience with LLM APIs and agentic workflows",
            "Strong Python or TypeScript skills",
            "Ability to translate business problems into AI-ready workflows",
        ],
        "active": True,
    },
    {
        "title": "Global Talent Recruiter",
        "department": "Global Recruitment",
        "location": "Warangal, IN",
        "type": "Full-time",
        "level": "Mid-level",
        "description": "Source, evaluate, and connect specialized talent with organizations across global markets.",
        "requirements": [
            "2+ years in technical or executive recruitment",
            "Excellent stakeholder communication",
            "Experience working across multiple geographies",
        ],
        "active": True,
    },
    {
        "title": "Product Designer",
        "department": "Software & Web Services",
        "location": "Remote — Global",
        "type": "Contract",
        "level": "Mid-level",
        "description": "Shape product experiences end-to-end — research, wireframes, and high-fidelity UI — for client SaaS products.",
        "requirements": [
            "Portfolio showing shipped product work",
            "Proficiency in Figma",
            "Experience partnering closely with engineers",
        ],
        "active": True,
    },
    {
        "title": "DevOps Engineer",
        "department": "Software & Web Services",
        "location": "Remote — Global",
        "type": "Full-time",
        "level": "Mid–Senior",
        "description": "Own CI/CD, infrastructure-as-code, and cloud reliability for client platforms at scale.",
        "requirements": [
            "Experience with Kubernetes and Terraform",
            "Strong scripting ability (Bash/Python)",
            "On-call incident response experience",
        ],
        "active": True,
    },
]

INSIGHTS = [
    {
        "title": "What AGI Foresight Means for Hiring in 2026",
        "category": "AI",
        "summary": "As AI capability curves shift, organizations are rethinking which roles to build in-house versus augment with intelligent systems.",
        "published": True,
    },
    {
        "title": "Building Global Teams Without Borders",
        "category": "Global Recruitment",
        "summary": "A look at how distributed hiring pipelines let organizations access specialized talent regardless of geography.",
        "published": True,
    },
    {
        "title": "From Idea to Production: Our SaaS Delivery Playbook",
        "category": "Software & Web Services",
        "summary": "How we take enterprise software from a whiteboard sketch to a scalable, production-ready platform.",
        "published": True,
    },
]

# Role definitions — used by the RBAC system in app.py.
# Each role lists the exact set of admin panel tabs it can see.
#
# Attendance: every role except "super_admin" (Admin) and "client" gets the
# "my_attendance" tab (personal check-in/check-out + monthly calendar).
# "super_admin" and "hr_manager" additionally get "attendance", the
# org-wide attendance register for reviewing everyone's hours.
ROLES = {
    "super_admin":      {"label": "Super Admin",       "tabs": ["overview","employees","performance","jobs","applications","pipeline","talent","contacts","newsletter","insights","activity","admin_users","attendance","reports_review","settings","my_profile"]},
    "hr_manager":       {"label": "HR Manager",        "tabs": ["overview","employees","performance","applications","pipeline","talent","contacts","my_attendance","attendance","daily_report","reports_review","settings","my_profile"]},
    "recruiter":        {"label": "Recruiter",         "tabs": ["overview","performance","applications","pipeline","talent","my_attendance","daily_report","my_profile"]},
    "team_lead":        {"label": "Team Lead",         "tabs": ["overview","performance","jobs","applications","my_attendance","daily_report","my_profile"]},
    "content_manager":  {"label": "Content Manager",   "tabs": ["overview","performance","insights","my_attendance","daily_report","my_profile"]},
    "viewer":           {"label": "Viewer",            "tabs": ["overview","performance","daily_report","my_profile"]},
    "employee":         {"label": "Employee",          "tabs": ["overview","my_attendance","daily_report","my_profile"]},
        "employee":         {"label": "Employee",          "tabs": ["overview","performance","my_attendance","daily_report","my_profile"]},
    "client":           {"label": "Client",            "tabs": ["overview"]},
}

# Roles required to punch in/out. Admin (super_admin), Client, and Viewer
# are intentionally excluded, per the attendance policy — Employee, HR
# Manager, Recruiter, Content Manager, and Team Lead all get attendance.
ATTENDANCE_ROLES = {"hr_manager", "recruiter", "content_manager", "team_lead", "employee"}

# Roles that get the WorkPulse-style "Daily Report" tab (submit a daily
# work report + see their own history). Every logged-in staff role gets
# this — everyone except Admin (super_admin, which instead gets the
# review side via "reports_review") and Client, per the same pattern
# used for ATTENDANCE_ROLES above.
DAILY_REPORT_ROLES = {"hr_manager", "recruiter", "content_manager", "team_lead", "employee", "viewer"}

# Roles that can review everyone's daily reports (leave a private comment,
# mark reviewed, see who hasn't submitted). Mirrors the HR Manager +
# Super Admin split already used for the attendance register.
REPORTS_REVIEW_ROLES = {"hr_manager"}


def seed():
    try:
        if not db.read("jobs"):
            for job in JOBS:
                db.insert("jobs", job)
            print("Seeded jobs.")

        if not db.read("insights"):
            for insight in INSIGHTS:
                db.insert("insights", insight)
            print("Seeded insights.")

        if not db.read("admins"):
            email = os.environ.get("ADMIN_EMAIL", "")
            password = os.environ.get("ADMIN_PASSWORD", "")

            if not email or not password:
                # No env vars set — generate random credentials and print once.
                email = "admin@kyktechnologies.com"
                password = secrets.token_urlsafe(18)
                print("=" * 60)
                print("  First-run admin credentials (save these now):")
                print(f"  Email:    {email}")
                print(f"  Password: {password}")
                print("  Set ADMIN_EMAIL + ADMIN_PASSWORD env vars to choose your own.")
                print("=" * 60)
            else:
                print(f"Seeded admin from environment: {email}")

            db.insert(
                "admins",
                {
                    "email": email,
                    "passwordHash": hash_password(password),
                    "name": "KYK Admin",
                    "role": "super_admin",
                },
            )
    except Exception as e:
        print(f"Warning: Database seeding skipped or failed during startup: {e}")


if __name__ == "__main__":
    seed()
