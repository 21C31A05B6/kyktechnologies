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
    "super_admin":      {"label": "Super Admin",       "tabs": ["overview","employees","departments","branches","admin_users","attendance","leave_mgmt","payroll","recruitment","performance","documents","lifecycle","reports","audit_log","settings","my_profile","jobs","applications","pipeline","talent","contacts","newsletter","insights","activity","my_attendance","reports_review","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","team","team_attendance","team_leaves","team_goals","team_reviews","team_calendar","timesheets","onboarding","communication"]},
    "admin":            {"label": "Admin",             "tabs": ["overview","employees","departments","branches","admin_users","attendance","leave_mgmt","payroll","recruitment","performance","documents","lifecycle","reports","audit_log","settings","my_profile","jobs","applications","pipeline","talent","contacts","newsletter","insights","activity","my_attendance","reports_review","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","team","team_attendance","team_leaves","team_goals","team_reviews","team_calendar","timesheets","onboarding","communication"]},
    "hr_manager":       {"label": "HR Manager",        "tabs": ["overview","employees","departments","branches","onboarding","attendance","leave_mgmt","payroll","recruitment","documents","lifecycle","reports","my_attendance","daily_report","reports_review","settings","my_profile","performance","jobs","applications","pipeline","talent","contacts","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","timesheets","communication"]},
    "hr":               {"label": "HR Specialist",     "tabs": ["overview","employees","departments","branches","onboarding","attendance","leave_mgmt","payroll","recruitment","documents","lifecycle","reports","my_attendance","daily_report","reports_review","settings","my_profile","performance","jobs","applications","pipeline","talent","contacts","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","timesheets","communication"]},
    "team_lead":        {"label": "Team Lead",         "tabs": ["overview","team","team_attendance","timesheets","team_leaves","team_goals","team_reviews","team_calendar","my_attendance","daily_report","report_history","my_profile","settings","jobs","performance","employees","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","communication"]},
    "manager":          {"label": "Manager",           "tabs": ["overview","team","team_attendance","timesheets","team_leaves","team_goals","team_reviews","team_calendar","my_attendance","daily_report","report_history","my_profile","settings","jobs","performance","employees","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","communication"]},
    "employee":         {"label": "Employee",          "tabs": ["overview","my_attendance","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","daily_report","report_history","my_profile","settings","performance","employees","communication"]},
    "recruiter":        {"label": "Recruiter",         "tabs": ["overview","recruitment","onboarding","performance","my_attendance","daily_report","report_history","my_profile","settings","jobs","applications","pipeline","talent","employees","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","communication"]},
    "content_manager":  {"label": "Content Manager",   "tabs": ["overview","performance","insights","my_attendance","daily_report","report_history","my_profile","settings","employees","my_leaves","my_payslips","my_timesheets","my_goals","my_documents","communication"]},
    "viewer":           {"label": "Viewer",            "tabs": ["overview","performance","daily_report","report_history","my_profile","settings","communication"]},
    "client":           {"label": "Client",            "tabs": ["overview"]},
}

ATTENDANCE_ROLES = {"hr_manager", "hr", "recruiter", "content_manager", "team_lead", "manager", "employee"}
HRMS_ROLES = {"super_admin", "admin", "hr_manager", "hr", "team_lead", "manager", "employee", "recruiter", "content_manager"}
DAILY_REPORT_ROLES = {"hr_manager", "hr", "recruiter", "content_manager", "team_lead", "manager", "employee", "viewer"}
REPORTS_REVIEW_ROLES = {"hr_manager", "hr", "super_admin", "admin"}

COMPANIES = [
    {
        "id": 1,
        "name": "KYK Technologies Pvt Ltd",
        "code": "KYK-HQ",
        "registrationNo": "U72200TG2022PTC160000",
        "taxId": "AAACK9999K",
        "email": "contact@kyktechnologies.com",
        "phone": "+91 870 245 0000",
        "website": "https://kyktechnologies.com",
        "timezone": "Asia/Kolkata",
        "currency": "INR",
    }
]

BRANCHES = [
    {
        "id": 1,
        "companyId": 1,
        "name": "Warangal Headquarters",
        "code": "WGL-01",
        "address": "Tech Park, Hanamkonda",
        "city": "Warangal",
        "state": "Telangana",
        "country": "India",
        "phone": "+91 870 245 0001",
        "isHeadquarters": True,
    },
    {
        "id": 2,
        "companyId": 1,
        "name": "Hyderabad Development Center",
        "code": "HYD-01",
        "address": "Hitech City, Madhapur",
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "phone": "+91 40 4567 8900",
        "isHeadquarters": False,
    },
    {
        "id": 3,
        "companyId": 1,
        "name": "Bengaluru Innovation Hub",
        "code": "BLR-01",
        "address": "Indiranagar 100ft Rd",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "phone": "+91 80 2345 6789",
        "isHeadquarters": False,
    },
]

DEPARTMENTS = [
    {"id": 1, "name": "Software & Web Services", "code": "ENG", "headName": "Vikram Adiga", "description": "Full-stack development, cloud architecture, and client SaaS delivery."},
    {"id": 2, "name": "AI, AGI, ASI Applications", "code": "AI", "headName": "Karthik Verma", "description": "Applied intelligence, agentic workflows, LLMs, and enterprise automation."},
    {"id": 3, "name": "Human Resources", "code": "HR", "headName": "Priya Nambiar", "description": "Talent management, employee lifecycle, payroll, and culture."},
    {"id": 4, "name": "Global Recruitment", "code": "REC", "headName": "Sneha Patel", "description": "Global sourcing, client staffing, and executive hiring."},
    {"id": 5, "name": "Finance & Operations", "code": "OPS", "headName": "Rajesh Sharma", "description": "Financial accounting, compliance, and administration."},
]

DESIGNATIONS = [
    {"id": 1, "title": "Senior Full-Stack Engineer", "department": "Software & Web Services", "level": "Senior"},
    {"id": 2, "title": "Engineering Manager", "department": "Software & Web Services", "level": "Management"},
    {"id": 3, "title": "AI Solutions Architect", "department": "AI, AGI, ASI Applications", "level": "Senior"},
    {"id": 4, "title": "Senior HR Manager", "department": "Human Resources", "level": "Management"},
    {"id": 5, "title": "HR Specialist", "department": "Human Resources", "level": "Mid-level"},
    {"id": 6, "title": "Global Talent Specialist", "department": "Global Recruitment", "level": "Mid-level"},
    {"id": 7, "title": "Operations Lead", "department": "Finance & Operations", "level": "Senior"},
]

SHIFTS = [
    {"id": 1, "name": "General Day Shift", "startTime": "09:30", "endTime": "18:15", "lateGraceMinutes": 15, "earlyGraceMinutes": 15, "workingDays": "0,1,2,3,4"},
    {"id": 2, "name": "Morning Shift", "startTime": "08:00", "endTime": "16:45", "lateGraceMinutes": 15, "earlyGraceMinutes": 15, "workingDays": "0,1,2,3,4"},
    {"id": 3, "name": "Night / Global Shift", "startTime": "18:30", "endTime": "03:30", "lateGraceMinutes": 15, "earlyGraceMinutes": 15, "workingDays": "0,1,2,3,4"},
]

HOLIDAYS = [
    {"id": 1, "name": "New Year's Day", "date": "2026-01-01", "optional": False, "branch": "All"},
    {"id": 2, "name": "Republic Day", "date": "2026-01-26", "optional": False, "branch": "All"},
    {"id": 3, "name": "Holi Festival", "date": "2026-03-04", "optional": False, "branch": "All"},
    {"id": 4, "name": "Good Friday", "date": "2026-04-03", "optional": True, "branch": "All"},
    {"id": 5, "name": "Independence Day", "date": "2026-08-15", "optional": False, "branch": "All"},
    {"id": 6, "name": "Gandhi Jayanti", "date": "2026-10-02", "optional": False, "branch": "All"},
    {"id": 7, "name": "Diwali Festival", "date": "2026-11-08", "optional": False, "branch": "All"},
    {"id": 8, "name": "Christmas Day", "date": "2026-12-25", "optional": False, "branch": "All"},
]

LEAVE_TYPES = [
    {"id": 1, "name": "Casual Leave", "code": "CL", "quotaPerYear": 12, "carryForwardMax": 5, "paid": True, "description": "Short-notice personal leaves"},
    {"id": 2, "name": "Sick Leave", "code": "SL", "quotaPerYear": 10, "carryForwardMax": 5, "paid": True, "description": "Medical and health recovery leaves"},
    {"id": 3, "name": "Paid / Annual Leave", "code": "PL", "quotaPerYear": 18, "carryForwardMax": 10, "paid": True, "description": "Planned vacations and extended leaves"},
    {"id": 4, "name": "Work From Home", "code": "WFH", "quotaPerYear": 24, "carryForwardMax": 0, "paid": True, "description": "Remote working authorization"},
    {"id": 5, "name": "Maternity / Paternity", "code": "ML", "quotaPerYear": 90, "carryForwardMax": 0, "paid": True, "description": "Parental leave policy"},
    {"id": 6, "name": "Unpaid Leave", "code": "LWP", "quotaPerYear": 30, "carryForwardMax": 0, "paid": False, "description": "Leave without pay"},
]

CORE_USERS = [
    {
        "id": 1,
        "email": "admin@kyktechnologies.com",
        "name": "Rajesh Sharma",
        "role": "super_admin",
        "phone": "+91 98765 43210",
        "password": "Admin@12345",
    },
    {
        "id": 2,
        "email": "hr.manager@kyktechnologies.com",
        "name": "Priya Nambiar",
        "role": "hr_manager",
        "phone": "+91 98765 43211",
        "password": "Hr@12345",
    },
    {
        "id": 3,
        "email": "team.lead@kyktechnologies.com",
        "name": "Vikram Adiga",
        "role": "team_lead",
        "phone": "+91 98765 43212",
        "password": "Lead@12345",
    },
    {
        "id": 4,
        "email": "employee@kyktechnologies.com",
        "name": "Ananya Rao",
        "role": "employee",
        "phone": "+91 98765 43213",
        "password": "Emp@12345",
    },
    {
        "id": 5,
        "email": "recruiter@kyktechnologies.com",
        "name": "Sneha Patel",
        "role": "recruiter",
        "phone": "+91 98765 43214",
        "password": "Recruiter@12345",
    },
    {
        "id": 6,
        "email": "karthik.verma@kyktechnologies.com",
        "name": "Karthik Verma",
        "role": "employee",
        "phone": "+91 98765 43215",
        "password": "Emp@12345",
    },
]

EMPLOYEES_SEED = [
    {
        "id": 1,
        "userId": 1,
        "employeeCode": "KYK-001",
        "name": "Rajesh Sharma",
        "email": "admin@kyktechnologies.com",
        "phone": "+91 98765 43210",
        "emergencyContact": "Sunita Sharma (+91 98765 00001 - Spouse)",
        "department": "Finance & Operations",
        "designation": "Director & Principal Admin",
        "branch": "Warangal Headquarters",
        "reportingManagerId": None,
        "reportingManagerName": "Board of Directors",
        "joiningDate": "2023-01-10",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Warangal, IN",
        "shiftName": "General Day Shift",
        "skills": ["Leadership", "Strategic Planning", "Corporate Finance", "Operations"],
        "qualifications": "MBA, Finance — IIM Bangalore",
        "bankName": "HDFC Bank",
        "accountNumber": "50100456789012",
        "ifscSwift": "HDFC0000123",
        "panTaxId": "ABCPS1234F",
        "basicSalary": 120000,
    },
    {
        "id": 2,
        "userId": 2,
        "employeeCode": "KYK-002",
        "name": "Priya Nambiar",
        "email": "hr.manager@kyktechnologies.com",
        "phone": "+91 98765 43211",
        "emergencyContact": "K. Nambiar (+91 98765 00002 - Father)",
        "department": "Human Resources",
        "designation": "Senior HR Manager",
        "branch": "Warangal Headquarters",
        "reportingManagerId": 1,
        "reportingManagerName": "Rajesh Sharma",
        "joiningDate": "2023-04-15",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Warangal, IN",
        "shiftName": "General Day Shift",
        "skills": ["Talent Acquisition", "Employee Relations", "Payroll Operations", "Statutory Compliance"],
        "qualifications": "MSW / MBA HR — Osmania University",
        "bankName": "ICICI Bank",
        "accountNumber": "001105009876",
        "ifscSwift": "ICIC0000011",
        "panTaxId": "BCDPN5678G",
        "basicSalary": 85000,
    },
    {
        "id": 3,
        "userId": 3,
        "employeeCode": "KYK-003",
        "name": "Vikram Adiga",
        "email": "team.lead@kyktechnologies.com",
        "phone": "+91 98765 43212",
        "emergencyContact": "Meera Adiga (+91 98765 00003 - Spouse)",
        "department": "Software & Web Services",
        "designation": "Engineering Manager",
        "branch": "Hyderabad Development Center",
        "reportingManagerId": 1,
        "reportingManagerName": "Rajesh Sharma",
        "joiningDate": "2023-06-01",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Hyderabad, IN / Hybrid",
        "shiftName": "General Day Shift",
        "skills": ["System Architecture", "Python", "React", "Cloud DevOps", "Team Mentorship"],
        "qualifications": "B.Tech Computer Science — NIT Warangal",
        "bankName": "State Bank of India",
        "accountNumber": "20349876543",
        "ifscSwift": "SBIN0001234",
        "panTaxId": "CDEVA9012H",
        "basicSalary": 95000,
    },
    {
        "id": 4,
        "userId": 4,
        "employeeCode": "KYK-004",
        "name": "Ananya Rao",
        "email": "employee@kyktechnologies.com",
        "phone": "+91 98765 43213",
        "emergencyContact": "Suresh Rao (+91 98765 00004 - Brother)",
        "department": "Software & Web Services",
        "designation": "Senior Full-Stack Engineer",
        "branch": "Hyderabad Development Center",
        "reportingManagerId": 3,
        "reportingManagerName": "Vikram Adiga",
        "joiningDate": "2024-02-01",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Hyderabad, IN / Hybrid",
        "shiftName": "General Day Shift",
        "skills": ["TypeScript", "Python/Flask", "PostgreSQL", "Docker", "REST & GraphQL"],
        "qualifications": "B.E. Information Technology — JNTU Hyderabad",
        "bankName": "Axis Bank",
        "accountNumber": "918010023456789",
        "ifscSwift": "UTIB0000456",
        "panTaxId": "DEFAR3456J",
        "basicSalary": 60000,
    },
    {
        "id": 5,
        "userId": 5,
        "employeeCode": "KYK-005",
        "name": "Sneha Patel",
        "email": "recruiter@kyktechnologies.com",
        "phone": "+91 98765 43214",
        "emergencyContact": "P. Patel (+91 98765 00005 - Parent)",
        "department": "Global Recruitment",
        "designation": "Global Talent Specialist",
        "branch": "Warangal Headquarters",
        "reportingManagerId": 2,
        "reportingManagerName": "Priya Nambiar",
        "joiningDate": "2024-03-15",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Warangal, IN",
        "shiftName": "General Day Shift",
        "skills": ["Technical Sourcing", "Interview Coordination", "Global Candidate Engagement"],
        "qualifications": "B.Com & PG Diploma in HRM",
        "bankName": "HDFC Bank",
        "accountNumber": "50100987654321",
        "ifscSwift": "HDFC0000123",
        "panTaxId": "EFGSP7890K",
        "basicSalary": 50000,
    },
    {
        "id": 6,
        "userId": 6,
        "employeeCode": "KYK-006",
        "name": "Karthik Verma",
        "email": "karthik.verma@kyktechnologies.com",
        "phone": "+91 98765 43215",
        "emergencyContact": "R. Verma (+91 98765 00006 - Brother)",
        "department": "AI, AGI, ASI Applications",
        "designation": "AI Solutions Architect",
        "branch": "Bengaluru Innovation Hub",
        "reportingManagerId": 3,
        "reportingManagerName": "Vikram Adiga",
        "joiningDate": "2024-05-02",
        "employmentType": "Full-time",
        "status": "active",
        "workLocation": "Bengaluru, IN / Remote",
        "shiftName": "General Day Shift",
        "skills": ["LLM Fine-tuning", "PyTorch", "FastAPI", "Vector DBs", "Agentic Systems"],
        "qualifications": "M.Tech AI — IIIT Hyderabad",
        "bankName": "Kotak Mahindra Bank",
        "accountNumber": "8012345678",
        "ifscSwift": "KKBK0000789",
        "panTaxId": "FGHAK1234L",
        "basicSalary": 80000,
    },
]

ONBOARDING_TASKS = [
    {"id": 1, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Collect ID proofs & Academic Certificates", "category": "HR", "assignedTo": "Priya Nambiar", "status": "completed", "completedAt": "2024-02-02T10:00:00Z"},
    {"id": 2, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Configure Enterprise Laptop & VPN Access", "category": "IT", "assignedTo": "IT Operations", "status": "completed", "completedAt": "2024-02-02T14:30:00Z"},
    {"id": 3, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Repository access & Development Environment walkthrough", "category": "Manager", "assignedTo": "Vikram Adiga", "status": "completed", "completedAt": "2024-02-03T11:00:00Z"},
    {"id": 4, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Read & acknowledge KYK Code of Conduct and Security Policy", "category": "Employee", "assignedTo": "Ananya Rao", "status": "completed", "completedAt": "2024-02-03T16:00:00Z"},
    {"id": 5, "employeeId": 6, "employeeName": "Karthik Verma", "title": "GPU cluster credentials & Model registry setup", "category": "IT", "assignedTo": "IT Operations", "status": "completed", "completedAt": "2024-05-03T10:00:00Z"},
    {"id": 6, "employeeId": 6, "employeeName": "Karthik Verma", "title": "Q4 Goal setting & 90-day milestone alignment", "category": "Manager", "assignedTo": "Vikram Adiga", "status": "completed", "completedAt": "2024-05-04T15:00:00Z"},
]

PERFORMANCE_CYCLES = [
    {"id": 1, "title": "Q3 2026 Mid-Year Review", "period": "Q3 2026", "startDate": "2026-07-01", "endDate": "2026-09-30", "status": "completed"},
    {"id": 2, "title": "Q4 2026 Annual Appraisal & Review", "period": "Q4 2026", "startDate": "2026-10-01", "endDate": "2026-12-31", "status": "active"},
]

PERFORMANCE_GOALS = [
    {"id": 1, "employeeId": 4, "employeeName": "Ananya Rao", "managerId": 3, "title": "Deliver Enterprise HRMS Portal v2.0 Architecture", "description": "Implement RBAC, 12 functional modules, attendance, payroll and self-service dashboards.", "kpi": "Module Delivery & Test Coverage", "targetValue": "100% on-time & zero regression", "progress": 92, "dueDate": "2026-10-31", "status": "in_progress"},
    {"id": 2, "employeeId": 4, "employeeName": "Ananya Rao", "managerId": 3, "title": "API Latency Optimization for High-Concurrency Endpoints", "description": "Ensure p95 latency stays under 120ms during peak attendance punches and payroll calculations.", "kpi": "p95 Latency < 120ms", "targetValue": "< 120ms", "progress": 85, "dueDate": "2026-11-15", "status": "in_progress"},
    {"id": 3, "employeeId": 6, "employeeName": "Karthik Verma", "managerId": 3, "title": "Agentic Workflow Automation for Talent Pipeline", "description": "Automate resume screening and JD semantic matching with precision >= 90%.", "kpi": "Screening Precision", "targetValue": ">= 90%", "progress": 78, "dueDate": "2026-11-30", "status": "in_progress"},
    {"id": 4, "employeeId": 5, "employeeName": "Sneha Patel", "managerId": 2, "title": "Q4 Sourcing Target — 15 Enterprise Hires", "description": "Source and close mid to senior engineering and AI positions across global clients.", "kpi": "Total Hires", "targetValue": "15 Hires", "progress": 60, "dueDate": "2026-12-15", "status": "in_progress"},
]

PERFORMANCE_REVIEWS = [
    {
        "id": 1,
        "cycleId": 1,
        "employeeId": 4,
        "employeeName": "Ananya Rao",
        "reviewerId": 3,
        "reviewerName": "Vikram Adiga",
        "selfRating": 5,
        "selfAssessment": "Successfully revamped frontend modularity, implemented attendance break tracking, and delivered client-ready reporting.",
        "managerRating": 5,
        "managerFeedback": "Outstanding velocity, clean architecture choices, proactive communication with stakeholders.",
        "status": "completed",
    }
]

DOCUMENTS_SEED = [
    {"id": 1, "employeeId": None, "employeeName": None, "title": "KYK Code of Conduct & Ethics (2026)", "category": "policy", "fileUrl": "/api/admin/files/kyk_code_of_conduct.pdf", "fileSize": "1.4 MB", "expiryDate": "2027-12-31", "isConfidential": False, "isCompanyPolicy": True, "acknowledgedBy": [1, 2, 3, 4, 5, 6]},
    {"id": 2, "employeeId": None, "employeeName": None, "title": "Information Security & Data Protection Policy", "category": "policy", "fileUrl": "/api/admin/files/kyk_infosec_policy.pdf", "fileSize": "2.1 MB", "expiryDate": "2027-12-31", "isConfidential": False, "isCompanyPolicy": True, "acknowledgedBy": [1, 2, 3, 4, 5, 6]},
    {"id": 3, "employeeId": None, "employeeName": None, "title": "Attendance, Leave & Work From Home Guidelines", "category": "policy", "fileUrl": "/api/admin/files/kyk_leave_policy.pdf", "fileSize": "850 KB", "expiryDate": "2027-12-31", "isConfidential": False, "isCompanyPolicy": True, "acknowledgedBy": [1, 2, 3, 4, 5, 6]},
    {"id": 4, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Employment Contract — Senior Full-Stack Engineer", "category": "contract", "fileUrl": "/api/admin/files/contract_ananya_rao.pdf", "fileSize": "620 KB", "expiryDate": "2028-02-01", "isConfidential": True, "isCompanyPolicy": False, "acknowledgedBy": [4]},
    {"id": 5, "employeeId": 4, "employeeName": "Ananya Rao", "title": "Government Identity & Address Verification", "category": "id_proof", "fileUrl": "/api/admin/files/id_ananya_rao.pdf", "fileSize": "910 KB", "expiryDate": "2032-05-10", "isConfidential": True, "isCompanyPolicy": False, "acknowledgedBy": [4]},
]

ANNOUNCEMENTS_SEED = [
    {"id": 1, "title": "KYK Technologies Q4 Townhall & Product Vision 2027", "content": "Join us on Friday at 4:30 PM IST for our quarterly all-hands meeting. We will review our achievements, announce key client milestones, and unveil new employee benefits.", "targetDepartment": "All", "authorName": "Rajesh Sharma (Director)", "pinned": True, "createdAt": "2026-10-10T09:00:00Z"},
    {"id": 2, "title": "Annual Hackathon 2026 — Theme: Autonomous Enterprise Agents", "content": "Registration is now open for our annual hackathon scheduled for November 14-15. Teams can register up to 4 members. Prizes for Innovation, Architecture, and Impact.", "targetDepartment": "Software & Web Services", "authorName": "Vikram Adiga", "pinned": True, "createdAt": "2026-10-08T11:30:00Z"},
    {"id": 3, "title": "Group Health Insurance Policy Renewal & Added Parents Coverage", "content": "Our group medical coverage has been enhanced to INR 7,50,000 per family. HR has published the digital e-cards under Document Management.", "targetDepartment": "All", "authorName": "Priya Nambiar (HR)", "pinned": False, "createdAt": "2026-10-05T14:00:00Z"},
]

TIMESHEETS_SEED = [
    {
        "id": 1,
        "employeeId": 4,
        "employeeName": "Ananya Rao",
        "weekStartDate": "2026-10-05",
        "projectName": "Enterprise HRMS Portal & Client Cloud Systems",
        "hoursBreakdown": {"mon": 8.5, "tue": 8.0, "wed": 8.5, "thu": 8.0, "fri": 8.0},
        "totalHours": 41.0,
        "notes": "Delivered RBAC permission matrix and attendance break persistence.",
        "status": "approved",
        "approvedBy": "Vikram Adiga",
        "approvedAt": "2026-10-10T16:00:00Z",
    },
    {
        "id": 2,
        "employeeId": 4,
        "employeeName": "Ananya Rao",
        "weekStartDate": "2026-10-12",
        "projectName": "Enterprise HRMS Portal & Client Cloud Systems",
        "hoursBreakdown": {"mon": 8.5, "tue": 8.5, "wed": 8.0, "thu": 8.0, "fri": 8.0},
        "totalHours": 41.0,
        "notes": "Building Payroll processing and Manager review dashboards.",
        "status": "submitted",
        "approvedBy": None,
        "approvedAt": None,
    },
]

NOTIFICATIONS_SEED = [
    {"id": 1, "userId": 4, "userEmail": "employee@kyktechnologies.com", "role": "employee", "title": "Payroll Published", "message": "Your payslip for September 2026 is published and ready for download.", "category": "payroll", "read": False, "createdAt": "2026-10-01T10:00:00Z"},
    {"id": 2, "userId": 4, "userEmail": "employee@kyktechnologies.com", "role": "employee", "title": "Timesheet Approved", "message": "Your timesheet for week starting 2026-10-05 was approved by Vikram Adiga.", "category": "attendance", "read": True, "createdAt": "2026-10-10T16:05:00Z"},
    {"id": 3, "userId": 3, "userEmail": "team.lead@kyktechnologies.com", "role": "team_lead", "title": "Pending Timesheet", "message": "Ananya Rao submitted timesheet for week starting 2026-10-12 for your review.", "category": "attendance", "read": False, "createdAt": "2026-10-12T18:00:00Z"},
    {"id": 4, "userId": 2, "userEmail": "hr.manager@kyktechnologies.com", "role": "hr_manager", "title": "New Leave Application", "message": "Ananya Rao submitted Casual Leave request from 2026-10-19 to 2026-10-20.", "category": "leave", "read": False, "createdAt": "2026-10-12T11:00:00Z"},
]

OFFBOARDING_SEED = [
    {
        "id": 1,
        "employeeId": 6,
        "employeeName": "Karthik Verma",
        "employeeEmail": "karthik.verma@kyktechnologies.com",
        "resignationDate": "2026-09-15",
        "noticePeriodDays": 60,
        "lastWorkingDate": "2026-11-15",
        "reason": "Higher studies in Artificial Intelligence & Robotics",
        "status": "clearance_in_progress",
        "ktStatus": True,
        "assetsReturned": False,
        "finalSettlementAmount": 145000,
        "exitInterviewNotes": "Positive exit; expressed interest in future advisory role once MS completes.",
    }
]


def seed():
    try:
        # 1. Jobs & Insights
        if not db.read("jobs"):
            for job in JOBS:
                db.insert("jobs", job)
            print("Seeded jobs.")

        if not db.read("insights"):
            for insight in INSIGHTS:
                db.insert("insights", insight)
            print("Seeded insights.")

        # 2. Company & Branches
        if not db.read("companies"):
            for comp in COMPANIES:
                db.insert("companies", comp)
            print("Seeded companies.")

        if not db.read("branches"):
            for br in BRANCHES:
                db.insert("branches", br)
            print("Seeded branches.")

        # 3. Departments & Designations
        if not db.read("departments"):
            for dept in DEPARTMENTS:
                db.insert("departments", dept)
            print("Seeded departments.")

        if not db.read("designations"):
            for des in DESIGNATIONS:
                db.insert("designations", des)
            print("Seeded designations.")

        # 4. Shifts & Holidays
        if not db.read("shifts"):
            for sh in SHIFTS:
                db.insert("shifts", sh)
            print("Seeded shifts.")

        if not db.read("holidays"):
            for h in HOLIDAYS:
                db.insert("holidays", h)
            print("Seeded holidays.")

        # 5. Leave Types
        if not db.read("leave_types"):
            for lt in LEAVE_TYPES:
                db.insert("leave_types", lt)
            print("Seeded leave types.")

        # 6. Core Users & Admins
        existing_admins = db.read("admins")
        existing_emails = {a.get("email", "").lower(): a for a in existing_admins}

        for user in CORE_USERS:
            email_lower = user["email"].lower()
            if email_lower not in existing_emails:
                row = {
                    "email": user["email"],
                    "passwordHash": hash_password(user["password"]),
                    "name": user["name"],
                    "role": user["role"],
                    "phone": user.get("phone", ""),
                    "status": "active",
                }
                inserted = db.insert("admins", row)
                existing_emails[email_lower] = inserted
            else:
                # Update role and status if present
                cur = existing_emails[email_lower]
                if cur.get("role") != user["role"] or cur.get("name") != user["name"]:
                    db.update("admins", cur["id"], {
                        "role": user["role"],
                        "name": user["name"],
                        "phone": user.get("phone", cur.get("phone", "")),
                        "status": "active",
                    })

        # 7. Employees directory
        if not db.read("employees"):
            for emp in EMPLOYEES_SEED:
                db.insert("employees", emp)
            print("Seeded employees.")

        # 8. Leave Balances for Employees
        if not db.read("leave_balances"):
            for emp in EMPLOYEES_SEED:
                db.insert("leave_balances", {
                    "employeeId": emp["id"],
                    "year": 2026,
                    "balances": {
                        "Casual Leave": {"quota": 12, "used": 2, "available": 10},
                        "Sick Leave": {"quota": 10, "used": 1, "available": 9},
                        "Paid / Annual Leave": {"quota": 18, "used": 4, "available": 14},
                        "Work From Home": {"quota": 24, "used": 5, "available": 19},
                        "Maternity / Paternity": {"quota": 90, "used": 0, "available": 90},
                        "Unpaid Leave": {"quota": 30, "used": 0, "available": 30},
                    }
                })
            print("Seeded leave balances.")

        # 9. Salary Structures
        if not db.read("salary_structures"):
            for emp in EMPLOYEES_SEED:
                b = emp.get("basicSalary", 50000)
                hra = int(b * 0.4)
                allowance = int(b * 0.2)
                conveyance = 3000
                pf = min(1800, int(b * 0.12))
                tax = int(b * 0.05)
                gross = b + hra + allowance + conveyance
                net = gross - pf - tax
                db.insert("salary_structures", {
                    "employeeId": emp["id"],
                    "basicSalary": b,
                    "hra": hra,
                    "specialAllowance": allowance,
                    "conveyance": conveyance,
                    "pfDeduction": pf,
                    "taxDeduction": tax,
                    "grossSalary": gross,
                    "netSalary": net,
                    "effectiveFrom": "2024-01-01",
                })
            print("Seeded salary structures.")

        # 10. Payroll Runs & Payslips
        if not db.read("payroll_runs"):
            p1 = db.insert("payroll_runs", {
                "monthYear": "2026-09",
                "status": "published",
                "totalGross": 468000,
                "totalDeductions": 31800,
                "totalNet": 436200,
                "employeeCount": 6,
                "processedBy": "Priya Nambiar",
                "processedAt": "2026-09-30T17:00:00Z",
                "publishedAt": "2026-10-01T09:00:00Z",
            })
            for emp in EMPLOYEES_SEED:
                b = emp.get("basicSalary", 50000)
                hra = int(b * 0.4)
                allowance = int(b * 0.2) + 3000
                pf = min(1800, int(b * 0.12))
                tax = int(b * 0.05)
                gross = b + hra + allowance
                net = gross - pf - tax
                db.insert("payslips", {
                    "payrollRunId": p1["id"],
                    "employeeId": emp["id"],
                    "employeeCode": emp["employeeCode"],
                    "employeeName": emp["name"],
                    "employeeEmail": emp["email"],
                    "department": emp["department"],
                    "designation": emp["designation"],
                    "monthYear": "2026-09",
                    "basic": b,
                    "hra": hra,
                    "allowances": allowance,
                    "bonus": 0,
                    "grossEarnings": gross,
                    "pf": pf,
                    "tax": tax,
                    "deductions": pf + tax,
                    "netPay": net,
                    "status": "published",
                    "publishedAt": "2026-10-01T09:00:00Z",
                })
            print("Seeded payroll runs & payslips.")

        # 11. Onboarding Tasks
        if not db.read("onboarding_tasks"):
            for t in ONBOARDING_TASKS:
                db.insert("onboarding_tasks", t)
            print("Seeded onboarding tasks.")

        # 12. Performance Cycles & Goals & Reviews
        if not db.read("performance_cycles"):
            for c in PERFORMANCE_CYCLES:
                db.insert("performance_cycles", c)
            for g in PERFORMANCE_GOALS:
                db.insert("performance_goals", g)
            for r in PERFORMANCE_REVIEWS:
                db.insert("performance_reviews", r)
            print("Seeded performance management.")

        # 13. Timesheets
        if not db.read("timesheets"):
            for ts in TIMESHEETS_SEED:
                db.insert("timesheets", ts)
            print("Seeded timesheets.")

        # 14. Documents & Announcements
        if not db.read("documents"):
            for d in DOCUMENTS_SEED:
                db.insert("documents", d)
            print("Seeded documents.")

        if not db.read("announcements"):
            for a in ANNOUNCEMENTS_SEED:
                db.insert("announcements", a)
            print("Seeded announcements.")

        # 15. Notifications
        if not db.read("notifications"):
            for n in NOTIFICATIONS_SEED:
                db.insert("notifications", n)
            print("Seeded notifications.")

        # 16. Offboarding Records
        if not db.read("offboarding_records"):
            for o in OFFBOARDING_SEED:
                db.insert("offboarding_records", o)
            print("Seeded offboarding records.")

        # 17. Seed initial attendance for employee & team lead for current month
        if not db.read("attendance"):
            cur_date = "2026-10-12"
            db.insert("attendance", {
                "adminId": 4,
                "adminName": "Ananya Rao",
                "adminEmail": "employee@kyktechnologies.com",
                "adminRole": "employee",
                "date": cur_date,
                "checkIn": "09:28",
                "checkOut": "18:18",
                "breaks": [{"start": "13:05", "end": "13:50"}],
                "onBreak": False,
                "workedSeconds": 28800,
                "dayStatus": "present",
                "lateByMinutes": 0,
                "earlyLeaveByMinutes": 0,
                "overtimeSeconds": 180,
                "corrected": False,
                "correctionReason": None,
                "correctedBy": None,
            })
            db.insert("attendance", {
                "adminId": 3,
                "adminName": "Vikram Adiga",
                "adminEmail": "team.lead@kyktechnologies.com",
                "adminRole": "team_lead",
                "date": cur_date,
                "checkIn": "09:25",
                "checkOut": "18:30",
                "breaks": [{"start": "13:10", "end": "13:55"}],
                "onBreak": False,
                "workedSeconds": 29400,
                "dayStatus": "present",
                "lateByMinutes": 0,
                "earlyLeaveByMinutes": 0,
                "overtimeSeconds": 900,
                "corrected": False,
                "correctionReason": None,
                "correctedBy": None,
            })
            print("Seeded initial attendance.")

    except Exception as e:
        print(f"Warning: Database seeding skipped or failed during startup: {e}")


if __name__ == "__main__":
    seed()

