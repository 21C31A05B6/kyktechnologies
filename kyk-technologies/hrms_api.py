"""hrms_api.py — Enterprise HRMS Portal API Routes (KYK Technologies).

Implements all 12 modules for the HRMS portal:
Module 1: Authentication and User Management (RBAC, account suspension, password reset)
Module 2: Employee Management (Profile CRUD, search/filter, import/export, history)
Module 3: Attendance and Timesheets (Clock in/out, corrections, timesheets & approvals)
Module 4: Leave Management (Leave types, balances, apply, collision checks, approvals)
Module 5: Payroll and Payslips (Salary structures, monthly runs, payslips generator & viewer)
Module 6: Recruitment and Onboarding (Job openings, candidates, 1-click hire, checklists)
Module 7: Performance Management (Appraisal cycles, goals & KPIs, self-assessments, reviews)
Module 8: Document Management (Categorized uploads, expiry tracking, policy consent)
Module 9: Notifications and Communication (Notification center, announcements)
Module 10: Reports and Analytics (Headcount, attendance, leaves, payroll totals, CSV exports)
Module 11: Employee Lifecycle and Offboarding (Resignation, exit checklist, final settlement)
Module 12: Administration and Audit (Company, branches, departments, designations, shifts, backup)
"""

import csv
import io
import json
import os
import secrets
import time
from datetime import datetime, timezone, date, timedelta
from flask import jsonify, request, Response

def register_hrms_routes(app, deps):
    db = deps["db"]
    clean = deps["clean"]
    error = deps["error"]
    audit = deps["audit"]
    valid_email = deps["valid_email"]
    hash_password = deps["hash_password"]
    verify_password = deps["verify_password"]
    current_admin = deps["current_admin"]
    ROLES = deps["ROLES"]
    SHIFT_SCHEDULES = deps["SHIFT_SCHEDULES"]
    COMPANY_TZ = deps["COMPANY_TZ"]
    _revoke_session = deps["_revoke_session"]

    HRMS_ALLOWED_ROLES = deps.get("HRMS_ALLOWED_ROLES", {
        "super_admin", "admin", "hr_manager", "hr",
        "team_lead", "manager", "employee", "recruiter", "content_manager"
    })

    def _norm_role(role):
        if role == "admin": return "super_admin"
        if role == "hr": return "hr_manager"
        if role == "manager": return "team_lead"
        return role

    def role_required(*allowed_roles):
        """Restrict to accounts with HRMS portal access:
        super_admin, admin, hr_manager, hr, team_lead, manager, employee, recruiter, content_manager.
        If specific allowed_roles are given, further restrict to those roles.
        Super admin and admin are always permitted.
        Completely rejects clients, viewers, general users, and non-HRMS accounts with 403."""
        def decorator(view):
            from functools import wraps
            @wraps(view)
            def wrapper(*args, **kwargs):
                admin = current_admin()
                if not admin:
                    return jsonify({"error": "Session expired. Please sign in again.", "kicked": True}), 401
                role = admin.get("role", "viewer")
                norm = _norm_role(role)
                if norm not in HRMS_ALLOWED_ROLES and role not in HRMS_ALLOWED_ROLES:
                    return error("HRMS Portal access is not available for your role.", 403)
                if norm != "super_admin" and role != "super_admin":
                    if allowed_roles and norm not in allowed_roles and role not in allowed_roles:
                        return error("You don't have permission to do that.", 403)
                request.admin = admin
                return view(*args, **kwargs)
            return wrapper
        return decorator

    def admin_required(view):
        """HRMS route wrapper: requires an active admin session with an HRMS-permitted role."""
        return role_required()(view)

    def _now_iso():
        return datetime.now(timezone.utc).isoformat()

    def _today_iso():
        return datetime.now(COMPANY_TZ).date().isoformat()

    # ─────────────────────────────────────────────────────────────────────────
    # Module 1: Authentication & User Management (RBAC & Account Controls)
    # ─────────────────────────────────────────────────────────────────────────

    @app.post("/api/auth/reset-password")
    def auth_reset_password():
        data = request.get_json(silent=True) or {}
        email = clean(data.get("email", ""), 160).lower()
        curr_pwd = str(data.get("currentPassword") or "")
        new_pwd = str(data.get("newPassword") or "")

        if not email or not new_pwd:
            return error("Email and new password are required.")
        if len(new_pwd) < 8:
            return error("New password must be at least 8 characters.")

        admin = None
        for a in db.read("admins"):
            if a.get("email", "").lower() == email:
                admin = a
                break

        if not admin:
            return error("Account not found with that email.", 404)

        # If current password was provided, verify it
        if curr_pwd and not verify_password(curr_pwd, admin.get("passwordHash", "")):
            return error("Current password does not match.", 403)

        db.update("admins", admin["id"], {
            "passwordHash": hash_password(new_pwd),
            "updatedAt": _now_iso(),
        })
        audit(admin, "password_reset", f"Password changed for {email}")
        return jsonify({"message": "Password reset successfully. Please log in with your new password."})

    @app.post("/api/admin/users/<int:user_id>/suspend")
    @role_required("hr_manager")
    def admin_suspend_user(user_id):
        data = request.get_json(silent=True) or {}
        new_status = clean(data.get("status", "suspended"), 30).lower()
        if new_status not in {"active", "suspended", "inactive"}:
            new_status = "suspended"

        user = db.find("admins", user_id)
        if not user:
            return error("User not found.", 404)
        if user_id == request.admin["id"]:
            return error("You cannot suspend your own account.")

        db.update("admins", user_id, {"status": new_status, "updatedAt": _now_iso()})
        audit(request.admin, "user_status_changed", f"User {user.get('email')} set to {new_status}")
        return jsonify({"message": f"User status updated to {new_status}.", "status": new_status})

    @app.post("/api/admin/users/<int:user_id>/reset-access")
    @role_required("hr_manager")
    def admin_reset_user_access(user_id):
        data = request.get_json(silent=True) or {}
        temp_pwd = str(data.get("newPassword") or "Welcome@2026")
        if len(temp_pwd) < 8:
            return error("Temporary password must be at least 8 characters.")

        user = db.find("admins", user_id)
        if not user:
            return error("User not found.", 404)

        db.update("admins", user_id, {
            "passwordHash": hash_password(temp_pwd),
            "status": "active",
            "updatedAt": _now_iso(),
        })
        audit(request.admin, "user_access_reset", f"Access reset for {user.get('email')}")
        return jsonify({"message": f"Password reset for {user.get('email')}.", "temporaryPassword": temp_pwd})

    @app.get("/api/admin/roles")
    @admin_required
    def admin_list_roles():
        role_list = []
        for key, meta in ROLES.items():
            role_list.append({
                "role": key,
                "label": meta.get("label", key),
                "tabs": meta.get("tabs", []),
            })
        return jsonify({"roles": role_list})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 2: Employee Management (Profile, CRUD, Search, Import/Export, History)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/admin/employees")
    @admin_required
    def get_employees_list():
        q = request.args.get("q", "").lower().strip()
        dept = request.args.get("department", "").strip()
        branch = request.args.get("branch", "").strip()
        status = request.args.get("status", "").strip()

        rows = db.read("employees")
        if not rows:
            rows = []

        filtered = []
        for emp in rows:
            if status and emp.get("status", "active").lower() != status.lower():
                continue
            if dept and emp.get("department", "").lower() != dept.lower():
                continue
            if branch and emp.get("branch", "").lower() != branch.lower():
                continue
            if q:
                name = emp.get("name", "").lower()
                email = emp.get("email", "").lower()
                code = emp.get("employeeCode", "").lower()
                desig = emp.get("designation", "").lower()
                if q not in name and q not in email and q not in code and q not in desig:
                    continue
        caller = request.admin
        caller_role = caller.get("role", "")
        norm_role = "super_admin" if caller_role in ("admin", "super_admin") else ("hr_manager" if caller_role in ("hr", "hr_manager") else caller_role)
        is_hr_or_super = norm_role in ("super_admin", "hr_manager")

        sanitized_filtered = []
        for emp in filtered:
            emp_copy = dict(emp)
            if not is_hr_or_super:
                for f in ("accountNumber", "ifscSwift", "panTaxId", "bankName"):
                    if f in emp_copy and emp_copy[f]:
                        val = str(emp_copy[f])
                        emp_copy[f] = f"***{val[-4:]}" if len(val) >= 4 else "***"
            sanitized_filtered.append(emp_copy)

        sanitized_filtered.sort(key=lambda e: e.get("name", ""))
        return jsonify({
            "employees": sanitized_filtered,
            "total": len(sanitized_filtered),
            "activeCount": len([e for e in rows if e.get("status", "active") == "active"]),
        })

    @app.post("/api/admin/employees")
    @role_required("hr_manager")
    def create_employee_profile():
        data = request.get_json(silent=True) or {}
        name = clean(data.get("name", ""), 150)
        email = clean(data.get("email", ""), 255).lower()
        if not name or not valid_email(email):
            return error("Full name and valid email are required.")

        existing = [e for e in db.read("employees") if e.get("email", "").lower() == email]
        if existing:
            return error("An employee record with this email already exists.")

        # Generate Employee Code
        all_emps = db.read("employees")
        code = clean(data.get("employeeCode", ""), 50)
        if not code:
            code = f"KYK-{len(all_emps) + 1:03d}"

        basic_salary = int(data.get("basicSalary") or 50000)
        emp_data = {
            "employeeCode": code,
            "name": name,
            "email": email,
            "phone": clean(data.get("phone", ""), 50),
            "emergencyContact": clean(data.get("emergencyContact", ""), 255),
            "department": clean(data.get("department", "Software & Web Services"), 100),
            "designation": clean(data.get("designation", "Software Engineer"), 100),
            "branch": clean(data.get("branch", "Warangal Headquarters"), 100),
            "reportingManagerId": data.get("reportingManagerId"),
            "reportingManagerName": clean(data.get("reportingManagerName", ""), 150),
            "joiningDate": clean(data.get("joiningDate", _today_iso()), 20),
            "employmentType": clean(data.get("employmentType", "Full-time"), 50),
            "status": clean(data.get("status", "active"), 50),
            "workLocation": clean(data.get("workLocation", "Warangal, IN"), 100),
            "shiftName": clean(data.get("shiftName", "General Day Shift"), 100),
            "skills": data.get("skills") if isinstance(data.get("skills"), list) else [s.strip() for s in str(data.get("skills", "")).split(",") if s.strip()],
            "qualifications": clean(data.get("qualifications", ""), 255),
            "bankName": clean(data.get("bankName", "HDFC Bank"), 100),
            "accountNumber": clean(data.get("accountNumber", ""), 50),
            "ifscSwift": clean(data.get("ifscSwift", ""), 50),
            "panTaxId": clean(data.get("panTaxId", ""), 50),
            "basicSalary": basic_salary,
            "photoUrl": clean(data.get("photoUrl", ""), 255),
            "createdAt": _now_iso(),
        }

        created = db.insert("employees", emp_data)

        # Initialize leave balances
        db.insert("leave_balances", {
            "employeeId": created["id"],
            "year": datetime.now(COMPANY_TZ).year,
            "balances": {
                "Casual Leave": {"quota": 12, "used": 0, "available": 12},
                "Sick Leave": {"quota": 10, "used": 0, "available": 10},
                "Paid / Annual Leave": {"quota": 18, "used": 0, "available": 18},
                "Work From Home": {"quota": 24, "used": 0, "available": 24},
                "Maternity / Paternity": {"quota": 90, "used": 0, "available": 90},
                "Unpaid Leave": {"quota": 30, "used": 0, "available": 30},
            }
        })

        # Initialize salary structure
        hra = int(basic_salary * 0.4)
        allowance = int(basic_salary * 0.2)
        conveyance = 3000
        pf = min(1800, int(basic_salary * 0.12))
        tax = int(basic_salary * 0.05)
        gross = basic_salary + hra + allowance + conveyance
        net = gross - pf - tax
        db.insert("salary_structures", {
            "employeeId": created["id"],
            "basicSalary": basic_salary,
            "hra": hra,
            "specialAllowance": allowance,
            "conveyance": conveyance,
            "pfDeduction": pf,
            "taxDeduction": tax,
            "grossSalary": gross,
            "netSalary": net,
            "effectiveFrom": emp_data["joiningDate"],
        })

        # Log Onboarding history
        db.insert("employment_history", {
            "employeeId": created["id"],
            "eventType": "onboarding",
            "fromValue": "New Hire",
            "toValue": f"{emp_data['designation']} ({emp_data['department']})",
            "effectiveDate": emp_data["joiningDate"],
            "remarks": "Employee profile created.",
            "recordedBy": request.admin.get("name", "HR"),
            "createdAt": _now_iso(),
        })

        # Optionally create portal login
        if data.get("createUser", True):
            user_pwd = str(data.get("userPassword") or "")
            if not user_pwd:
                user_pwd = secrets.token_urlsafe(12)
            role = clean(data.get("role", "employee"), 50)
            if not any(a.get("email", "").lower() == email for a in db.read("admins")):
                db.insert("admins", {
                    "name": name,
                    "email": email,
                    "passwordHash": hash_password(user_pwd),
                    "role": role if role in ROLES else "employee",
                    "status": "active",
                    "mustResetPassword": True,
                    "phone": emp_data["phone"],
                    "department": emp_data["department"],
                    "designation": emp_data["designation"],
                })

        audit(request.admin, "employee_created", f"{name} ({code})")
        return jsonify(created), 201

    @app.get("/api/admin/employees/<int:emp_id>")
    @admin_required
    def get_single_employee(emp_id):
        emp = db.find("employees", emp_id)
        if not emp:
            return error("Employee not found.", 404)

        # Attach balances, salary structure, and history
        balances = next((b for b in db.read("leave_balances") if b.get("employeeId") == emp_id), None)
        salary = next((s for s in db.read("salary_structures") if s.get("employeeId") == emp_id), None)
        history = [h for h in db.read("employment_history") if h.get("employeeId") == emp_id]
        history.sort(key=lambda h: h.get("effectiveDate", ""), reverse=True)

        caller = request.admin
        caller_role = caller.get("role", "")
        norm_role = "super_admin" if caller_role in ("admin", "super_admin") else ("hr_manager" if caller_role in ("hr", "hr_manager") else caller_role)
        is_hr_or_super = norm_role in ("super_admin", "hr_manager")
        is_self = caller.get("email", "").lower() == emp.get("email", "").lower()

        emp_copy = dict(emp)
        # HR-07: field-level privacy for sensitive bank and tax identifiers
        if not (is_hr_or_super or is_self):
            for f in ("accountNumber", "ifscSwift", "panTaxId", "bankName"):
                if f in emp_copy and emp_copy[f]:
                    val = str(emp_copy[f])
                    emp_copy[f] = f"***{val[-4:]}" if len(val) >= 4 else "***"

        return jsonify({
            "employee": emp_copy,
            "leaveBalances": balances.get("balances", {}) if balances else {},
            "salaryStructure": salary if (is_hr_or_super or is_self) else {},
            "history": history,
        })

    @app.put("/api/admin/employees/<int:emp_id>")
    @role_required("hr_manager")
    def update_employee_profile(emp_id):
        emp = db.find("employees", emp_id)
        if not emp:
            return error("Employee not found.", 404)

        data = request.get_json(silent=True) or {}
        patch = {}
        for k in ["name", "phone", "emergencyContact", "branch", "reportingManagerId",
                  "reportingManagerName", "employmentType", "status", "workLocation",
                  "shiftName", "qualifications", "bankName", "accountNumber", "ifscSwift", "panTaxId"]:
            if k in data:
                patch[k] = clean(data[k], 255)

        if "skills" in data:
            patch["skills"] = data["skills"] if isinstance(data["skills"], list) else [s.strip() for s in str(data["skills"]).split(",") if s.strip()]

        # Track department / designation changes in history
        old_dept = emp.get("department", "")
        old_desig = emp.get("designation", "")
        new_dept = clean(data.get("department", old_dept), 100)
        new_desig = clean(data.get("designation", old_desig), 100)

        if (new_dept != old_dept or new_desig != old_desig) and (new_dept or new_desig):
            patch["department"] = new_dept
            patch["designation"] = new_desig
            db.insert("employment_history", {
                "employeeId": emp_id,
                "eventType": "promotion" if "senior" in new_desig.lower() or "lead" in new_desig.lower() else "transfer",
                "fromValue": f"{old_desig} ({old_dept})",
                "toValue": f"{new_desig} ({new_dept})",
                "effectiveDate": clean(data.get("effectiveDate", _today_iso()), 20),
                "remarks": clean(data.get("remarks", "Role or department change updated by HR"), 300),
                "recordedBy": request.admin.get("name", "HR"),
                "createdAt": _now_iso(),
            })

        if "basicSalary" in data:
            new_salary = int(data["basicSalary"] or 0)
            if new_salary > 0 and new_salary != emp.get("basicSalary", 0):
                patch["basicSalary"] = new_salary
                db.insert("employment_history", {
                    "employeeId": emp_id,
                    "eventType": "salary_revision",
                    "fromValue": f"INR {emp.get('basicSalary', 0):,}",
                    "toValue": f"INR {new_salary:,}",
                    "effectiveDate": _today_iso(),
                    "remarks": "Salary revised by HR.",
                    "recordedBy": request.admin.get("name", "HR"),
                    "createdAt": _now_iso(),
                })

        patch["updatedAt"] = _now_iso()
        updated = db.update("employees", emp_id, patch)
        audit(request.admin, "employee_updated", f"Updated employee {emp.get('name')} ({emp_id})")
        return jsonify(updated)

    @app.delete("/api/admin/employees/<int:emp_id>")
    @role_required("hr_manager")
    def deactivate_employee(emp_id):
        emp = db.find("employees", emp_id)
        if not emp:
            return error("Employee not found.", 404)

        db.update("employees", emp_id, {"status": "inactive", "updatedAt": _now_iso()})
        # If admin account exists, suspend it
        for a in db.read("admins"):
            if a.get("email", "").lower() == emp.get("email", "").lower():
                db.update("admins", a["id"], {"status": "inactive"})
                break

        audit(request.admin, "employee_deactivated", f"Deactivated {emp.get('name')} ({emp_id})")
        return jsonify({"message": "Employee deactivated successfully."})

    @app.get("/api/admin/employees/export.csv")
    @role_required("hr_manager")
    def export_employees_csv():
        employees = db.read("employees")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Employee Code", "Full Name", "Email", "Phone", "Department",
            "Designation", "Branch", "Joining Date", "Employment Type", "Status",
            "Basic Salary", "Bank Name", "Account Number", "PAN/Tax ID"
        ])
        for e in employees:
            writer.writerow([
                e.get("employeeCode", ""), e.get("name", ""), e.get("email", ""),
                e.get("phone", ""), e.get("department", ""), e.get("designation", ""),
                e.get("branch", ""), e.get("joiningDate", ""), e.get("employmentType", ""),
                e.get("status", "active"), e.get("basicSalary", ""), e.get("bankName", ""),
                e.get("accountNumber", ""), e.get("panTaxId", "")
            ])
        output = buf.getvalue()
        return Response(output, mimetype="text/csv", headers={
            "Content-Disposition": f"attachment; filename=kyk_employees_{_today_iso()}.csv"
        })

    @app.post("/api/admin/employees/import")
    @role_required("hr_manager")
    def import_employees():
        data = request.get_json(silent=True) or {}
        items = data.get("employees", [])
        if not isinstance(items, list) or not items:
            return error("Provide a list of employee objects under 'employees'.")

        imported_count = 0
        for item in items:
            name = clean(item.get("name", ""), 150)
            email = clean(item.get("email", ""), 255).lower()
            if not name or not valid_email(email):
                continue
            if any(e.get("email", "").lower() == email for e in db.read("employees")):
                continue
            code = clean(item.get("employeeCode", ""), 50) or f"KYK-{len(db.read('employees')) + 1:03d}"
            db.insert("employees", {
                "employeeCode": code,
                "name": name,
                "email": email,
                "phone": clean(item.get("phone", ""), 50),
                "department": clean(item.get("department", "Software & Web Services"), 100),
                "designation": clean(item.get("designation", "Software Engineer"), 100),
                "branch": clean(item.get("branch", "Warangal Headquarters"), 100),
                "joiningDate": clean(item.get("joiningDate", _today_iso()), 20),
                "status": "active",
                "basicSalary": int(item.get("basicSalary") or 50000),
                "createdAt": _now_iso(),
            })
            imported_count += 1

        audit(request.admin, "employees_imported", f"Imported {imported_count} employees")
        return jsonify({"message": f"Successfully imported {imported_count} employee records."})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 3: Attendance Corrections & Timesheets
    # ─────────────────────────────────────────────────────────────────────────

    @app.post("/api/attendance/correction-request")
    @admin_required
    def request_attendance_correction():
        data = request.get_json(silent=True) or {}
        date_str = clean(data.get("date", ""), 20)
        req_in = clean(data.get("checkIn", ""), 10)
        req_out = clean(data.get("checkOut", ""), 10)
        reason = clean(data.get("reason", ""), 300)

        if not date_str or not reason:
            return error("Date and reason for correction are required.")

        admin = request.admin
        correction = db.insert("attendance_corrections", {
            "employeeId": admin["id"],
            "employeeName": admin.get("name", ""),
            "employeeEmail": admin.get("email", ""),
            "date": date_str,
            "requestedCheckIn": req_in,
            "requestedCheckOut": req_out,
            "reason": reason,
            "status": "pending",
            "submittedAt": _now_iso(),
        })

        # Send notification to HR
        db.insert("notifications", {
            "role": "hr_manager",
            "title": "Attendance Correction Request",
            "message": f"{admin.get('name')} requested attendance correction for {date_str}.",
            "category": "attendance",
            "read": False,
            "createdAt": _now_iso(),
        })

        audit(admin, "attendance_correction_requested", f"{date_str} ({reason})")
        return jsonify(correction), 201

    @app.get("/api/admin/attendance/corrections")
    @role_required("hr_manager", "team_lead")
    def list_attendance_corrections():
        status = request.args.get("status", "")
        rows = db.read("attendance_corrections") or []
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: r.get("submittedAt", ""), reverse=True)
        return jsonify(rows)

    @app.post("/api/admin/attendance/corrections/<int:corr_id>/decide")
    @role_required("hr_manager")
    def decide_attendance_correction(corr_id):
        corr = db.find("attendance_corrections", corr_id)
        if not corr:
            return error("Correction request not found.", 404)
        if corr.get("status") != "pending":
            return error("This request has already been processed.")

        data = request.get_json(silent=True) or {}
        decision = clean(data.get("decision", ""), 20).lower()
        if decision not in {"approved", "rejected"}:
            return error("Decision must be 'approved' or 'rejected'.")

        db.update("attendance_corrections", corr_id, {
            "status": decision,
            "decidedBy": request.admin.get("name", "HR"),
            "decidedAt": _now_iso(),
            "comments": clean(data.get("comments", ""), 300),
        })

        if decision == "approved":
            # Find and update corresponding attendance record
            att_records = db.read("attendance")
            target = next((a for a in att_records if (a.get("adminId") == corr.get("employeeId") or a.get("userId") == corr.get("employeeId")) and a.get("date") == corr.get("date")), None)
            if target:
                db.update("attendance", target["id"], {
                    "originalCheckIn": target.get("originalCheckIn") or target.get("checkIn"),
                    "originalCheckOut": target.get("originalCheckOut") or target.get("checkOut"),
                    "checkIn": corr.get("requestedCheckIn") or target.get("checkIn"),
                    "checkOut": corr.get("requestedCheckOut") or target.get("checkOut"),
                    "corrected": True,
                    "correctedBy": request.admin.get("name", "HR"),
                    "correctionReason": corr.get("reason"),
                    "dayStatus": "present",
                })
            else:
                db.insert("attendance", {
                    "adminId": corr.get("employeeId"),
                    "adminName": corr.get("employeeName"),
                    "adminEmail": corr.get("employeeEmail"),
                    "date": corr.get("date"),
                    "checkIn": corr.get("requestedCheckIn", "09:30"),
                    "checkOut": corr.get("requestedCheckOut", "18:15"),
                    "workedSeconds": 28800,
                    "dayStatus": "present",
                    "corrected": True,
                    "correctedBy": request.admin.get("name", "HR"),
                    "correctionReason": corr.get("reason"),
                })

        # Notify employee
        db.insert("notifications", {
            "userId": corr.get("employeeId"),
            "userEmail": corr.get("employeeEmail"),
            "title": f"Attendance Correction {decision.capitalize()}",
            "message": f"Your correction request for {corr.get('date')} was {decision} by HR.",
            "category": "attendance",
            "read": False,
            "createdAt": _now_iso(),
        })

        audit(request.admin, "attendance_correction_decision", f"Correction {corr_id}: {decision}")
        return jsonify({"message": f"Correction request {decision}."})

    # Timesheets
    @app.post("/api/timesheets/submit")
    @admin_required
    def submit_timesheet():
        data = request.get_json(silent=True) or {}
        week_start = clean(data.get("weekStartDate", ""), 20)
        project = clean(data.get("projectName", ""), 150)
        hours = data.get("hoursBreakdown", {})
        total_hours = float(data.get("totalHours") or sum(float(v or 0) for v in hours.values()))
        notes = clean(data.get("notes", ""), 500)

        if not week_start or not project:
            return error("Week start date and project name are required.")

        admin = request.admin
        row = db.insert("timesheets", {
            "employeeId": admin["id"],
            "employeeName": admin.get("name", "Staff"),
            "employeeEmail": admin.get("email", ""),
            "weekStartDate": week_start,
            "projectName": project,
            "hoursBreakdown": hours,
            "totalHours": total_hours,
            "notes": notes,
            "status": "submitted",
            "submittedAt": _now_iso(),
        })

        audit(admin, "timesheet_submitted", f"Week {week_start} ({total_hours} hrs)")
        return jsonify(row), 201

    @app.get("/api/timesheets/my")
    @admin_required
    def get_my_timesheets():
        my_id = request.admin["id"]
        rows = [t for t in db.read("timesheets") if t.get("employeeId") == my_id]
        rows.sort(key=lambda t: t.get("weekStartDate", ""), reverse=True)
        return jsonify(rows)

    @app.get("/api/manager/timesheets")
    @role_required("team_lead", "hr_manager")
    def get_manager_timesheets():
        rows = db.read("timesheets") or []
        rows.sort(key=lambda t: t.get("weekStartDate", ""), reverse=True)
        return jsonify(rows)

    @app.post("/api/manager/timesheets/<int:ts_id>/decide")
    @role_required("team_lead", "hr_manager")
    def decide_timesheet(ts_id):
        ts = db.find("timesheets", ts_id)
        if not ts:
            return error("Timesheet not found.", 404)

        data = request.get_json(silent=True) or {}
        decision = clean(data.get("decision", "approved"), 20).lower()
        if decision not in {"approved", "rejected"}:
            return error("Decision must be 'approved' or 'rejected'.")

        updated = db.update("timesheets", ts_id, {
            "status": decision,
            "approvedBy": request.admin.get("name", "Manager"),
            "approvedAt": _now_iso(),
            "comments": clean(data.get("comments", ""), 300),
        })

        # Send notification to employee
        db.insert("notifications", {
            "userId": ts.get("employeeId"),
            "userEmail": ts.get("employeeEmail"),
            "title": f"Timesheet {decision.capitalize()}",
            "message": f"Your timesheet for week starting {ts.get('weekStartDate')} was {decision}.",
            "category": "attendance",
            "read": False,
            "createdAt": _now_iso(),
        })

        audit(request.admin, "timesheet_decision", f"Timesheet {ts_id}: {decision}")
        return jsonify(updated)

    @app.get("/api/admin/attendance/reports")
    @role_required("hr_manager", "team_lead")
    def get_attendance_reports():
        records = db.read("attendance") or []
        total_records = len(records)
        present = len([r for r in records if r.get("dayStatus") == "present"])
        absent = len([r for r in records if r.get("dayStatus") == "absent"])
        late = len([r for r in records if (r.get("lateByMinutes") or 0) > 0])
        total_worked_seconds = sum(r.get("workedSeconds", 0) for r in records)
        avg_hours = round(total_worked_seconds / 3600 / max(1, present), 1)

        return jsonify({
            "totalRecords": total_records,
            "present": present,
            "absent": absent,
            "lateArrivals": late,
            "averageHours": avg_hours,
            "punctualityRate": f"{round((present - late) / max(1, present) * 100, 1)}%",
        })

    @app.get("/api/manager/team")
    @role_required("team_lead", "hr_manager")
    def get_manager_team():
        admin = request.admin
        my_dept = admin.get("department")
        employees = db.read("employees") or []
        att_today = [a for a in (db.read("attendance") or []) if a.get("date") == _today_iso()]
        leaves_today = [l for l in (db.read("leave_requests") or []) if l.get("status") == "approved" and l.get("fromDate", "") <= _today_iso() <= l.get("toDate", "")]

        team = []
        for e in employees:
            if admin.get("role") in {"super_admin", "admin", "hr_manager"} or not my_dept or e.get("department") == my_dept:
                is_present = any(a.get("adminEmail", "").lower() == e.get("email", "").lower() or a.get("adminId") == e.get("id") for a in att_today)
                is_leave = any(l.get("employeeEmail", "").lower() == e.get("email", "").lower() or l.get("adminId") == e.get("id") for l in leaves_today)
                team.append({
                    **e,
                    "presentToday": is_present,
                    "onLeaveToday": is_leave,
                })
        return jsonify(team)

    @app.get("/api/manager/team-attendance")
    @role_required("team_lead", "hr_manager")
    def get_manager_team_attendance():
        req_date = clean(request.args.get("date", _today_iso()), 20)
        admin = request.admin
        my_dept = admin.get("department")
        employees = db.read("employees") or []
        dept_emps = [e for e in employees if admin.get("role") in {"super_admin", "admin", "hr_manager"} or not my_dept or e.get("department") == my_dept]

        att_rows = [a for a in (db.read("attendance") or []) if a.get("date") == req_date]
        leaves = [l for l in (db.read("leave_requests") or []) if l.get("status") == "approved" and l.get("fromDate", "") <= req_date <= l.get("toDate", "")]

        rows = []
        present_cnt = 0
        late_cnt = 0
        leave_cnt = 0
        absent_cnt = 0

        for e in dept_emps:
            email = e.get("email", "").lower()
            punch = next((a for a in att_rows if (a.get("adminEmail", "").lower() == email or a.get("adminId") == e.get("id"))), None)
            on_leave = any((l.get("employeeEmail", "").lower() == email or l.get("adminId") == e.get("id")) for l in leaves)

            if punch:
                present_cnt += 1
                if (punch.get("lateByMinutes") or 0) > 0:
                    late_cnt += 1
                status = punch.get("dayStatus", "present")
                worked_hrs = round((punch.get("workedSeconds") or 0) / 3600, 1)
            elif on_leave:
                leave_cnt += 1
                status = "on_leave"
                worked_hrs = 0
            else:
                absent_cnt += 1
                status = "absent"
                worked_hrs = 0

            rows.append({
                "employeeName": e.get("name", "Staff"),
                "employeeEmail": email,
                "shiftName": e.get("shift", "General Shift"),
                "checkIn": punch.get("checkIn") if punch else None,
                "checkOut": punch.get("checkOut") if punch else None,
                "workedHours": worked_hrs if punch else None,
                "dayStatus": status,
            })

        return jsonify({
            "present": present_cnt,
            "late": late_cnt,
            "onLeave": leave_cnt,
            "absent": absent_cnt,
            "rows": rows,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Module 4: Leave Management (Types, Balances, Multi-level Approval, Calendar)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/leave/types")
    @admin_required
    def get_leave_types():
        return jsonify(db.read("leave_types") or [])

    @app.post("/api/leave/types")
    @role_required("hr_manager")
    def create_leave_type():
        data = request.get_json(silent=True) or {}
        name = clean(data.get("name", ""), 100)
        code = clean(data.get("code", ""), 20).upper()
        if not name or not code:
            return error("Name and code are required.")

        item = db.insert("leave_types", {
            "name": name,
            "code": code,
            "quotaPerYear": int(data.get("quotaPerYear") or 12),
            "carryForwardMax": int(data.get("carryForwardMax") or 5),
            "paid": bool(data.get("paid", True)),
            "description": clean(data.get("description", ""), 255),
        })
        audit(request.admin, "leave_type_created", name)
        return jsonify(item), 201

    @app.get("/api/leave/balances")
    @admin_required
    def get_my_leave_balances():
        admin = request.admin
        balances = next((b for b in db.read("leave_balances") if b.get("employeeId") == admin["id"]), None)
        if not balances:
            # Fallback default balance
            default_b = {
                "Casual Leave": {"quota": 12, "used": 0, "available": 12},
                "Sick Leave": {"quota": 10, "used": 0, "available": 10},
                "Paid / Annual Leave": {"quota": 18, "used": 0, "available": 18},
                "Work From Home": {"quota": 24, "used": 0, "available": 24},
            }
            return jsonify({"balances": default_b})
        return jsonify({"balances": balances.get("balances", {})})

    @app.get("/api/admin/leave/balances/<int:emp_id>")
    @role_required("hr_manager", "team_lead")
    def get_emp_leave_balances(emp_id):
        b = next((x for x in db.read("leave_balances") if x.get("employeeId") == emp_id), None)
        return jsonify(b or {"balances": {}})

    @app.put("/api/admin/leave/balances/<int:emp_id>")
    @role_required("hr_manager")
    def update_emp_leave_balances(emp_id):
        data = request.get_json(silent=True) or {}
        b = next((x for x in db.read("leave_balances") if x.get("employeeId") == emp_id), None)
        if b:
            updated = db.update("leave_balances", b["id"], {"balances": data.get("balances", {})})
            return jsonify(updated)
        else:
            created = db.insert("leave_balances", {
                "employeeId": emp_id,
                "year": datetime.now(COMPANY_TZ).year,
                "balances": data.get("balances", {}),
            })
            return jsonify(created)

    @app.post("/api/leave/cancel/<int:leave_id>")
    @admin_required
    def cancel_leave_request(leave_id):
        req = db.find("leave_requests", leave_id)
        if not req:
            return error("Leave request not found.", 404)
        if req.get("adminId") != request.admin["id"] and request.admin.get("role") not in {"super_admin", "admin", "hr_manager"}:
            return error("You can only cancel your own leave requests.", 403)
        if req.get("status") not in {"pending", "approved"}:
            return error("Cannot cancel a completed or rejected leave.")

        updated = db.update("leave_requests", leave_id, {"status": "cancelled"})
        audit(request.admin, "leave_cancelled", f"Leave {leave_id}")
        return jsonify(updated)

    @app.get("/api/manager/leave")
    @role_required("team_lead", "hr_manager")
    def get_manager_team_leaves():
        rows = db.read("leave_requests") or []
        rows.sort(key=lambda r: r.get("fromDate", ""), reverse=True)
        return jsonify(rows)

    @app.get("/api/leave/team-calendar")
    @admin_required
    def get_team_leave_calendar():
        leaves = [r for r in db.read("leave_requests") if r.get("status") in {"approved", "pending"}]
        holidays = db.read("holidays") or []
        return jsonify({"leaves": leaves, "holidays": holidays})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 5: Payroll & Payslips (Structures, Monthly Runs, Clean Slip Generator)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/payroll/salary-structures")
    @role_required("hr_manager")
    def list_salary_structures():
        return jsonify(db.read("salary_structures") or [])

    @app.get("/api/payroll/salary-structures/<int:emp_id>")
    @admin_required
    def get_emp_salary_structure(emp_id):
        if request.admin["id"] != emp_id and request.admin.get("role") not in {"super_admin", "admin", "hr_manager"}:
            return error("Access denied.", 403)
        s = next((x for x in db.read("salary_structures") if x.get("employeeId") == emp_id), None)
        return jsonify(s or {})

    @app.post("/api/payroll/salary-structures")
    @role_required("hr_manager")
    def save_salary_structure():
        data = request.get_json(silent=True) or {}
        emp_id = data.get("employeeId")
        if not emp_id:
            return error("Employee ID is required.")

        basic = int(data.get("basicSalary") or 0)
        hra = int(data.get("hra") or int(basic * 0.4))
        special = int(data.get("specialAllowance") or int(basic * 0.2))
        conveyance = int(data.get("conveyance") or 3000)
        pf = int(data.get("pfDeduction") or min(1800, int(basic * 0.12)))
        tax = int(data.get("taxDeduction") or int(basic * 0.05))
        gross = basic + hra + special + conveyance
        net = gross - pf - tax

        struct_data = {
            "employeeId": emp_id,
            "basicSalary": basic,
            "hra": hra,
            "specialAllowance": special,
            "conveyance": conveyance,
            "pfDeduction": pf,
            "taxDeduction": tax,
            "grossSalary": gross,
            "netSalary": net,
            "effectiveFrom": clean(data.get("effectiveFrom", _today_iso()), 20),
            "updatedAt": _now_iso(),
        }

        existing = next((x for x in db.read("salary_structures") if x.get("employeeId") == emp_id), None)
        if existing:
            saved = db.update("salary_structures", existing["id"], struct_data)
        else:
            saved = db.insert("salary_structures", struct_data)

        # Update basic salary on employee model
        db.update("employees", emp_id, {"basicSalary": basic})
        audit(request.admin, "salary_structure_updated", f"Employee {emp_id}: Net INR {net:,}")
        return jsonify(saved)

    @app.get("/api/payroll/runs")
    @role_required("hr_manager")
    def list_payroll_runs():
        runs = db.read("payroll_runs") or []
        runs.sort(key=lambda r: r.get("monthYear", ""), reverse=True)
        return jsonify(runs)

    @app.post("/api/payroll/runs")
    @role_required("hr_manager")
    def process_payroll_run():
        data = request.get_json(silent=True) or {}
        month_year = clean(data.get("monthYear", ""), 20)
        if not month_year or len(month_year) != 7 or "-" not in month_year:
            return error("Month year must be in format YYYY-MM (e.g. 2026-10).")

        existing_run = next((r for r in db.read("payroll_runs") if r.get("monthYear") == month_year), None)
        if existing_run and existing_run.get("status") == "published":
            return error(f"Payroll for {month_year} is already finalized and published.")

        employees = [e for e in db.read("employees") if e.get("status", "active") == "active"]
        if not employees:
            return error("No active employees found to process payroll.")

        total_gross = 0
        total_deductions = 0
        total_net = 0

        # Create or update run record
        run_record = existing_run or db.insert("payroll_runs", {
            "monthYear": month_year,
            "status": "draft",
            "totalGross": 0,
            "totalDeductions": 0,
            "totalNet": 0,
            "employeeCount": len(employees),
            "processedBy": request.admin.get("name", "HR"),
            "processedAt": _now_iso(),
        })

        # Calculate payslip for each employee
        for emp in employees:
            struct = next((s for s in db.read("salary_structures") if s.get("employeeId") == emp["id"]), None)
            basic = struct.get("basicSalary", emp.get("basicSalary", 50000)) if struct else emp.get("basicSalary", 50000)
            hra = struct.get("hra", int(basic * 0.4)) if struct else int(basic * 0.4)
            allowances = struct.get("specialAllowance", int(basic * 0.2)) + struct.get("conveyance", 3000) if struct else int(basic * 0.2) + 3000
            pf = struct.get("pfDeduction", min(1800, int(basic * 0.12))) if struct else min(1800, int(basic * 0.12))
            tax = struct.get("taxDeduction", int(basic * 0.05)) if struct else int(basic * 0.05)
            gross = basic + hra + allowances
            deductions = pf + tax
            net = gross - deductions

            total_gross += gross
            total_deductions += deductions
            total_net += net

            # Check if payslip already exists for this run and employee
            existing_slip = next((p for p in db.read("payslips") if p.get("payrollRunId") == run_record["id"] and p.get("employeeId") == emp["id"]), None)
            slip_data = {
                "payrollRunId": run_record["id"],
                "employeeId": emp["id"],
                "employeeCode": emp.get("employeeCode", f"KYK-{emp['id']:03d}"),
                "employeeName": emp.get("name", "Staff"),
                "employeeEmail": emp.get("email", ""),
                "department": emp.get("department", "Engineering"),
                "designation": emp.get("designation", "Staff"),
                "monthYear": month_year,
                "basic": basic,
                "hra": hra,
                "allowances": allowances,
                "bonus": 0,
                "grossEarnings": gross,
                "pf": pf,
                "tax": tax,
                "deductions": deductions,
                "netPay": net,
                "status": "draft",
            }
            if existing_slip:
                db.update("payslips", existing_slip["id"], slip_data)
            else:
                db.insert("payslips", slip_data)

        updated_run = db.update("payroll_runs", run_record["id"], {
            "totalGross": total_gross,
            "totalDeductions": total_deductions,
            "totalNet": total_net,
            "employeeCount": len(employees),
            "status": "calculated",
        })

        audit(request.admin, "payroll_processed", f"{month_year} (Gross: {total_gross:,}, Net: {total_net:,})")
        return jsonify(updated_run)

    @app.get("/api/payroll/runs/<int:run_id>")
    @role_required("hr_manager")
    def get_payroll_run_details(run_id):
        run = db.find("payroll_runs", run_id)
        if not run:
            return error("Payroll run not found.", 404)
        slips = [p for p in db.read("payslips") if p.get("payrollRunId") == run_id]
        return jsonify({"run": run, "payslips": slips})

    @app.post("/api/payroll/runs/<int:run_id>/approve")
    @role_required("hr_manager")
    def approve_payroll_run(run_id):
        run = db.find("payroll_runs", run_id)
        if not run:
            return error("Payroll run not found.", 404)
        updated = db.update("payroll_runs", run_id, {"status": "approved", "approvedAt": _now_iso()})
        audit(request.admin, "payroll_approved", f"Run {run.get('monthYear')}")
        return jsonify(updated)

    @app.post("/api/payroll/runs/<int:run_id>/publish")
    @role_required("hr_manager")
    def publish_payroll_run(run_id):
        run = db.find("payroll_runs", run_id)
        if not run:
            return error("Payroll run not found.", 404)

        now_str = _now_iso()
        db.update("payroll_runs", run_id, {"status": "published", "publishedAt": now_str})

        # Mark all child payslips published and send notifications
        slips = [p for p in db.read("payslips") if p.get("payrollRunId") == run_id]
        for s in slips:
            db.update("payslips", s["id"], {"status": "published", "publishedAt": now_str})
            db.insert("notifications", {
                "userId": s.get("employeeId"),
                "userEmail": s.get("employeeEmail"),
                "title": f"Payslip Published — {run.get('monthYear')}",
                "message": f"Your salary slip for {run.get('monthYear')} is now available for download. Net Pay: INR {s.get('netPay', 0):,}",
                "category": "payroll",
                "read": False,
                "createdAt": now_str,
            })

        audit(request.admin, "payroll_published", f"Run {run.get('monthYear')} ({len(slips)} payslips)")
        return jsonify({"message": f"Payroll published. {len(slips)} payslips are now live."})

    @app.get("/api/payslips/my")
    @admin_required
    def get_my_payslips():
        admin = request.admin
        my_email = admin.get("email", "").lower()
        my_id = admin["id"]
        slips = [p for p in db.read("payslips") if (p.get("employeeEmail", "").lower() == my_email or p.get("employeeId") == my_id) and p.get("status") == "published"]
        slips.sort(key=lambda p: p.get("monthYear", ""), reverse=True)
        return jsonify(slips)

    @app.get("/api/payslips/<int:slip_id>")
    @admin_required
    def get_single_payslip(slip_id):
        slip = db.find("payslips", slip_id)
        if not slip:
            return error("Payslip not found.", 404)

        admin = request.admin
        if slip.get("employeeEmail", "").lower() != admin.get("email", "").lower() and slip.get("employeeId") != admin["id"] and admin.get("role") not in {"super_admin", "admin", "hr_manager"}:
            return error("You are not authorized to view this payslip.", 403)

        company = (db.read("companies") or [{}])[0]
        return jsonify({"payslip": slip, "company": company})

    @app.get("/api/admin/payroll/summary")
    @role_required("hr_manager")
    def get_payroll_summary():
        runs = db.read("payroll_runs") or []
        slips = db.read("payslips") or []
        last_run = next((r for r in sorted(runs, key=lambda x: x.get("monthYear", ""), reverse=True) if r.get("status") == "published"), None)
        dept_costs = {}
        for s in slips:
            if last_run and s.get("payrollRunId") == last_run.get("id"):
                d = s.get("department", "Other")
                dept_costs[d] = dept_costs.get(d, 0) + s.get("grossEarnings", 0)

        return jsonify({
            "latestMonth": last_run.get("monthYear") if last_run else "—",
            "totalGross": last_run.get("totalGross", 0) if last_run else 0,
            "totalNet": last_run.get("totalNet", 0) if last_run else 0,
            "departmentCosts": dept_costs,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Module 6: Recruitment & Onboarding (Jobs, 1-Click Hire, Checklists)
    # ─────────────────────────────────────────────────────────────────────────

    @app.post("/api/recruitment/candidates/<int:cand_id>/convert-to-employee")
    @role_required("hr_manager", "recruiter")
    def convert_candidate_to_employee(cand_id):
        cand = db.find("applications", cand_id) or db.find("talent", cand_id)
        if not cand:
            return error("Candidate application not found.", 404)

        data = request.get_json(silent=True) or {}
        name = cand.get("name") or "New Hire"
        email = cand.get("email") or ""
        dept = clean(data.get("department", cand.get("jobTitle", "Software & Web Services")), 100)
        desig = clean(data.get("designation", cand.get("jobTitle", "Software Engineer")), 100)
        salary = int(data.get("basicSalary") or 55000)

        all_emps = db.read("employees")
        code = f"KYK-{len(all_emps) + 1:03d}"

        emp = db.insert("employees", {
            "employeeCode": code,
            "name": name,
            "email": email,
            "phone": cand.get("phone", ""),
            "department": dept,
            "designation": desig,
            "branch": clean(data.get("branch", "Warangal Headquarters"), 100),
            "joiningDate": clean(data.get("joiningDate", _today_iso()), 20),
            "employmentType": "Full-time",
            "status": "active",
            "basicSalary": salary,
            "createdAt": _now_iso(),
        })

        # Update candidate status
        if db.find("applications", cand_id):
            db.update("applications", cand_id, {"status": "hired", "convertedToEmployeeId": emp["id"]})

        # Initialize onboarding checklist
        standard_tasks = [
            ("Collect Government ID & Academic Credentials", "HR", "Priya Nambiar"),
            ("Provision Corporate Email & VPN Credentials", "IT", "IT Admin"),
            ("Configure Developer Laptop & Security Tokens", "IT", "IT Admin"),
            ("Schedule Manager 1:1 & Milestone Alignment", "Manager", "Vikram Adiga"),
            ("Review & Sign KYK Code of Conduct and NDA", "Employee", name),
        ]
        for title, cat, assignee in standard_tasks:
            db.insert("onboarding_tasks", {
                "employeeId": emp["id"],
                "employeeName": name,
                "title": title,
                "category": cat,
                "assignedTo": assignee,
                "status": "pending",
            })

        # Initialize leave balances
        db.insert("leave_balances", {
            "employeeId": emp["id"],
            "year": datetime.now(COMPANY_TZ).year,
            "balances": {
                "Casual Leave": {"quota": 12, "used": 0, "available": 12},
                "Sick Leave": {"quota": 10, "used": 0, "available": 10},
                "Paid / Annual Leave": {"quota": 18, "used": 0, "available": 18},
                "Work From Home": {"quota": 24, "used": 0, "available": 24},
            }
        })

        # Create user account with secure temporary credentials (HR-02)
        temp_pwd = str(data.get("password") or "")
        if not temp_pwd:
            temp_pwd = secrets.token_urlsafe(12)
        if not any(a.get("email", "").lower() == email.lower() for a in db.read("admins")):
            db.insert("admins", {
                "name": name,
                "email": email,
                "passwordHash": hash_password(temp_pwd),
                "role": "employee",
                "status": "active",
                "mustResetPassword": True,
                "department": dept,
                "designation": desig,
            })

        audit(request.admin, "candidate_hired", f"{name} hired as {desig} ({code})")
        return jsonify({
            "message": f"{name} converted to employee successfully.",
            "employee": emp,
            "accountCreated": True,
        })

    @app.get("/api/onboarding/tasks")
    @admin_required
    def list_onboarding_tasks():
        """List onboarding tasks without side effects (HR-05) and scoped by role (HR-04)."""
        caller = request.admin
        caller_role = caller.get("role", "")
        norm_role = "super_admin" if caller_role in ("admin", "super_admin") else ("hr_manager" if caller_role in ("hr", "hr_manager") else caller_role)

        rows = db.read("onboarding_tasks") or []

        # If caller is an employee, strictly limit to their own onboarding tasks (HR-04)
        if norm_role == "employee":
            emp = next((e for e in db.read("employees") if e.get("email", "").lower() == caller.get("email", "").lower()), None)
            emp_id = emp["id"] if emp else -1
            rows = [r for r in rows if str(r.get("employeeId")) == str(emp_id)]
            return jsonify(rows)

        emp_id = request.args.get("employeeId")
        if emp_id:
            rows = [r for r in rows if str(r.get("employeeId")) == str(emp_id)]
        return jsonify(rows)

    @app.get("/api/employee/onboarding/tasks")
    @admin_required
    def get_my_onboarding_tasks():
        """Dedicated employee-scoped onboarding task listing (HR-04)."""
        caller = request.admin
        emp = next((e for e in db.read("employees") if e.get("email", "").lower() == caller.get("email", "").lower()), None)
        if not emp:
            return jsonify([])
        rows = [r for r in db.read("onboarding_tasks") if str(r.get("employeeId")) == str(emp["id"])]
        return jsonify(rows)

    @app.post("/api/onboarding/tasks")
    @role_required("hr_manager", "recruiter")
    def create_onboarding_task():
        data = request.get_json(silent=True) or {}
        emp_id = data.get("employeeId")
        title = clean(data.get("title", ""), 200)
        if not emp_id or not title:
            return error("Employee ID and task title are required.")

        emp = db.find("employees", emp_id)
        task = db.insert("onboarding_tasks", {
            "employeeId": emp_id,
            "employeeName": emp.get("name") if emp else "Staff",
            "title": title,
            "category": clean(data.get("category", "HR"), 50),
            "assignedTo": clean(data.get("assignedTo", "HR"), 150),
            "dueDate": clean(data.get("dueDate", ""), 20),
            "status": "pending",
        })
        return jsonify(task), 201

    @app.post("/api/onboarding/tasks/<int:task_id>/complete")
    @admin_required
    def complete_onboarding_task(task_id):
        t = db.find("onboarding_tasks", task_id)
        if not t:
            return error("Task not found.", 404)
        updated = db.update("onboarding_tasks", task_id, {
            "status": "completed",
            "completedAt": _now_iso(),
            "completedBy": request.admin.get("name", "Staff"),
        })
        return jsonify(updated)

    # ─────────────────────────────────────────────────────────────────────────
    # Module 7: Performance Management (Cycles, Goals & KPIs, Reviews)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/performance/cycles")
    @admin_required
    def list_performance_cycles():
        return jsonify(db.read("performance_cycles") or [])

    @app.post("/api/performance/cycles")
    @role_required("hr_manager")
    def create_performance_cycle():
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", ""), 150)
        period = clean(data.get("period", ""), 50)
        if not title or not period:
            return error("Cycle title and period are required.")

        cycle = db.insert("performance_cycles", {
            "title": title,
            "period": period,
            "startDate": clean(data.get("startDate", _today_iso()), 20),
            "endDate": clean(data.get("endDate", ""), 20),
            "status": "active",
        })
        audit(request.admin, "performance_cycle_created", title)
        return jsonify(cycle), 201

    @app.get("/api/performance/goals")
    @admin_required
    def list_performance_goals():
        emp_id = request.args.get("employeeId")
        goals = db.read("performance_goals") or []
        if emp_id:
            goals = [g for g in goals if str(g.get("employeeId")) == str(emp_id)]
        elif request.admin.get("role") == "employee":
            goals = [g for g in goals if g.get("employeeId") == request.admin["id"]]
        return jsonify(goals)

    @app.post("/api/performance/goals")
    @admin_required
    def create_performance_goal():
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", ""), 200)
        emp_id = data.get("employeeId") or request.admin["id"]
        if not title:
            return error("Goal title is required.")

        emp = db.find("employees", emp_id)
        goal = db.insert("performance_goals", {
            "employeeId": emp_id,
            "employeeName": emp.get("name") if emp else request.admin.get("name", ""),
            "managerId": data.get("managerId"),
            "title": title,
            "description": clean(data.get("description", ""), 500),
            "kpi": clean(data.get("kpi", "Milestone Target"), 150),
            "targetValue": clean(data.get("targetValue", "100%"), 100),
            "progress": int(data.get("progress") or 0),
            "dueDate": clean(data.get("dueDate", ""), 20),
            "status": clean(data.get("status", "in_progress"), 50),
        })
        return jsonify(goal), 201

    @app.post("/api/performance/goals/<int:goal_id>/progress")
    @admin_required
    def update_goal_progress(goal_id):
        g = db.find("performance_goals", goal_id)
        if not g:
            return error("Goal not found.", 404)

        data = request.get_json(silent=True) or {}
        prog = min(100, max(0, int(data.get("progress", g.get("progress", 0)))))
        status = "completed" if prog == 100 else ("in_progress" if prog > 0 else "not_started")

        updated = db.update("performance_goals", goal_id, {"progress": prog, "status": status})
        return jsonify(updated)

    @app.get("/api/performance/reviews")
    @admin_required
    def list_performance_reviews():
        emp_id = request.args.get("employeeId")
        reviews = db.read("performance_reviews") or []
        if emp_id:
            reviews = [r for r in reviews if str(r.get("employeeId")) == str(emp_id)]
        return jsonify(reviews)

    @app.post("/api/performance/reviews")
    @admin_required
    def submit_performance_review():
        data = request.get_json(silent=True) or {}
        emp_id = data.get("employeeId") or request.admin["id"]
        emp = db.find("employees", emp_id)
        admin = request.admin

        rev = db.insert("performance_reviews", {
            "cycleId": data.get("cycleId"),
            "employeeId": emp_id,
            "employeeName": emp.get("name") if emp else admin.get("name", ""),
            "reviewerId": admin["id"],
            "reviewerName": admin.get("name", ""),
            "selfRating": int(data.get("selfRating") or 4),
            "selfAssessment": clean(data.get("selfAssessment", ""), 1000),
            "managerRating": int(data.get("managerRating") or 4),
            "managerFeedback": clean(data.get("managerFeedback", ""), 1000),
            "status": "completed" if data.get("managerRating") else "submitted",
            "createdAt": _now_iso(),
        })
        audit(admin, "performance_review_submitted", f"Employee {emp_id}")
        return jsonify(rev), 201

    @app.get("/api/performance/team-goals")
    @role_required("team_lead", "hr_manager")
    def get_performance_team_goals():
        goals = db.read("performance_goals") or []
        admin = request.admin
        my_dept = admin.get("department")
        if admin.get("role") in {"super_admin", "admin", "hr_manager"} or not my_dept:
            return jsonify(goals)
        dept_emp_ids = {e.get("id") for e in (db.read("employees") or []) if e.get("department") == my_dept}
        filtered = [g for g in goals if g.get("employeeId") in dept_emp_ids or g.get("managerId") == admin["id"]]
        return jsonify(filtered)

    @app.post("/api/performance/team-goals")
    @role_required("team_lead", "hr_manager")
    def create_performance_team_goal():
        data = request.get_json(silent=True) or {}
        emp_id = data.get("employeeId")
        title = clean(data.get("title", ""), 200)
        metric = clean(data.get("metricTarget", data.get("kpi", "100%")), 100)
        desc = clean(data.get("description", ""), 500)
        if not emp_id or not title:
            return error("Employee ID and goal title are required.")
        emp = db.find("employees", emp_id)
        g = db.insert("performance_goals", {
            "employeeId": emp_id,
            "employeeName": emp.get("name") if emp else "Staff",
            "managerId": request.admin["id"],
            "title": title,
            "description": desc,
            "metricTarget": metric,
            "progressPercent": 0,
            "status": "in_progress",
            "createdAt": _now_iso(),
        })
        return jsonify(g), 201

    @app.get("/api/performance/team-reviews")
    @role_required("team_lead", "hr_manager")
    def get_performance_team_reviews():
        reviews = db.read("performance_reviews") or []
        return jsonify(reviews)

    @app.get("/api/performance/my-goals")
    @admin_required
    def get_my_performance_goals():
        admin = request.admin
        my_id = admin["id"]
        goals = [g for g in (db.read("performance_goals") or []) if g.get("employeeId") == my_id]
        return jsonify(goals)

    @app.get("/api/performance/my-reviews")
    @admin_required
    def get_my_performance_reviews():
        admin = request.admin
        my_id = admin["id"]
        reviews = [r for r in (db.read("performance_reviews") or []) if r.get("employeeId") == my_id]
        return jsonify(reviews)

    @app.post("/api/performance/reviews/<int:rev_id>/submit-self")
    @admin_required
    def submit_self_review_endpoint(rev_id):
        rev = db.find("performance_reviews", rev_id)
        if not rev:
            return error("Performance review record not found.", 404)
        data = request.get_json(silent=True) or {}
        self_summary = clean(data.get("selfAssessment", ""), 1000)
        self_rating = int(data.get("selfRating") or 5)
        updated = db.update("performance_reviews", rev_id, {
            "selfAssessment": self_summary,
            "selfRating": self_rating,
            "status": "submitted",
            "selfSubmittedAt": _now_iso(),
        })
        return jsonify(updated)

    @app.post("/api/performance/goals/<int:goal_id>/update")
    @admin_required
    def update_goal_progress_percent(goal_id):
        g = db.find("performance_goals", goal_id)
        if not g:
            return error("Goal not found.", 404)
        data = request.get_json(silent=True) or {}
        pct = min(100, max(0, int(data.get("progressPercent", data.get("progress", 0)))))
        updated = db.update("performance_goals", goal_id, {
            "progressPercent": pct,
            "progress": pct,
            "status": "completed" if pct >= 100 else "in_progress"
        })
        return jsonify(updated)

    # ─────────────────────────────────────────────────────────────────────────
    # Module 8: Document Management (Categorized, Expiration Tracker, Policies)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/documents")
    @app.get("/api/documents/all")
    @admin_required
    def list_documents():
        category = request.args.get("category", "")
        emp_id = request.args.get("employeeId")
        docs = db.read("documents") or []
        today = date.today()
        for d in docs:
            exp_str = d.get("expiryDate")
            if exp_str:
                try:
                    exp_d = date.fromisoformat(str(exp_str)[:10])
                    days_left = (exp_d - today).days
                    d["daysToExpiry"] = days_left
                    d["expiringSoon"] = 0 <= days_left <= 30
                except Exception:
                    d["daysToExpiry"] = 999
                    d["expiringSoon"] = False
            else:
                d["daysToExpiry"] = 999
                d["expiringSoon"] = False
        if category:
            docs = [d for d in docs if d.get("category") == category]
        if emp_id:
            docs = [d for d in docs if str(d.get("employeeId")) == str(emp_id)]
        elif request.admin.get("role") == "employee":
            # Employee sees their own documents plus company policies
            docs = [d for d in docs if d.get("employeeId") == request.admin["id"] or d.get("isCompanyPolicy", False)]
        return jsonify(docs)

    @app.get("/api/documents/my")
    @admin_required
    def list_my_documents():
        my_id = request.admin["id"]
        docs = [d for d in (db.read("documents") or []) if d.get("employeeId") == my_id]
        return jsonify(docs)

    @app.post("/api/documents")
    @app.post("/api/documents/all")
    @admin_required
    def upload_document_record():
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", ""), 200)
        file_url = clean(data.get("fileUrl", ""), 255) or "/api/admin/files/document_placeholder.pdf"
        if not title:
            return error("Document title is required.")

        admin = request.admin
        is_policy = bool(data.get("isCompanyPolicy", False))
        doc = db.insert("documents", {
            "employeeId": data.get("employeeId") if not is_policy else None,
            "employeeName": clean(data.get("employeeName", ""), 150) if not is_policy else None,
            "title": title,
            "category": clean(data.get("category", "policy" if is_policy else "other"), 50),
            "fileUrl": file_url,
            "fileSize": clean(data.get("fileSize", "1.1 MB"), 50),
            "expiryDate": clean(data.get("expiryDate", ""), 20) or None,
            "isConfidential": bool(data.get("isConfidential", False)),
            "isCompanyPolicy": is_policy,
            "acknowledgedBy": [],
            "createdAt": _now_iso(),
        })
        audit(admin, "document_uploaded", title)
        return jsonify(doc), 201

    @app.delete("/api/documents/<int:doc_id>")
    @role_required("hr_manager")
    def delete_document(doc_id):
        d = db.find("documents", doc_id)
        if not d:
            return error("Document not found.", 404)
        db.remove("documents", doc_id)
        audit(request.admin, "document_deleted", d.get("title", ""))
        return jsonify({"message": "Document deleted."})

    @app.get("/api/documents/policies")
    @admin_required
    def list_policies():
        policies = [d for d in (db.read("documents") or []) if d.get("isCompanyPolicy", False) or d.get("category") == "policy"]
        my_id = request.admin["id"]
        for p in policies:
            is_ack = my_id in (p.get("acknowledgedBy") or [])
            p["acknowledged"] = is_ack
            p["isAcknowledged"] = is_ack
        return jsonify(policies)

    @app.post("/api/documents/policies/<int:policy_id>/acknowledge")
    @admin_required
    def acknowledge_policy(policy_id):
        p = db.find("documents", policy_id)
        if not p:
            return error("Policy document not found.", 404)

        ack_list = p.get("acknowledgedBy") or []
        my_id = request.admin["id"]
        if my_id not in ack_list:
            ack_list.append(my_id)
            db.update("documents", policy_id, {"acknowledgedBy": ack_list})

        audit(request.admin, "policy_acknowledged", p.get("title", ""))
        return jsonify({"message": "Policy acknowledged successfully.", "acknowledged": True})

    @app.get("/api/documents/expiring")
    @role_required("hr_manager")
    def list_expiring_documents():
        docs = db.read("documents") or []
        today = date.today()
        threshold = today + timedelta(days=45)
        expiring = []
        for d in docs:
            exp_str = d.get("expiryDate")
            if exp_str:
                try:
                    exp_date = date.fromisoformat(exp_str)
                    if today <= exp_date <= threshold:
                        d["daysLeft"] = (exp_date - today).days
                        expiring.append(d)
                except ValueError:
                    pass
        return jsonify(expiring)

    # ─────────────────────────────────────────────────────────────────────────
    # Module 9: Notifications & Company Communication
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/notifications")
    @admin_required
    def get_user_notifications():
        admin = request.admin
        my_id = admin["id"]
        my_email = admin.get("email", "").lower()
        my_role = admin.get("role", "employee")

        all_notifs = db.read("notifications") or []
        user_notifs = [
            n for n in all_notifs
            if n.get("userId") == my_id or n.get("userEmail", "").lower() == my_email or n.get("role") in {my_role, "all"}
        ]
        user_notifs.sort(key=lambda n: n.get("createdAt", ""), reverse=True)
        return jsonify(user_notifs[:30])

    @app.post("/api/notifications/<int:notif_id>/read")
    @admin_required
    def mark_notification_read(notif_id):
        db.update("notifications", notif_id, {"read": True})
        return jsonify({"read": True})

    @app.post("/api/notifications/read-all")
    @app.post("/api/notifications/mark-read")
    @admin_required
    def mark_all_notifications_read():
        admin = request.admin
        my_id = admin["id"]
        my_email = admin.get("email", "").lower()
        for n in db.read("notifications") or []:
            if n.get("userId") == my_id or n.get("userEmail", "").lower() == my_email or admin.get("role") in {"super_admin", "admin"}:
                db.update("notifications", n["id"], {"read": True})
        return jsonify({"message": "All marked as read."})

    @app.get("/api/announcements")
    @admin_required
    def list_announcements():
        rows = db.read("announcements") or []
        rows.sort(key=lambda a: (not a.get("pinned", False), a.get("createdAt", "")), reverse=True)
        return jsonify(rows)

    @app.post("/api/announcements")
    @role_required("hr_manager")
    def post_announcement():
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", ""), 200)
        content = clean(data.get("content", ""), 2000)
        if not title or not content:
            return error("Title and content are required.")

        ann = db.insert("announcements", {
            "title": title,
            "content": content,
            "targetDepartment": clean(data.get("targetDepartment", "All"), 100),
            "authorName": request.admin.get("name", "HR Management"),
            "pinned": bool(data.get("pinned", True)),
            "createdAt": _now_iso(),
        })

        # Broadcast notification
        db.insert("notifications", {
            "role": "all",
            "title": f"Announcement: {title}",
            "message": content[:120] + "...",
            "category": "announcement",
            "read": False,
            "createdAt": _now_iso(),
        })

        audit(request.admin, "announcement_posted", title)
        return jsonify(ann), 201

    @app.delete("/api/announcements/<int:ann_id>")
    @role_required("hr_manager")
    def delete_announcement(ann_id):
        db.remove("announcements", ann_id)
        return jsonify({"message": "Announcement deleted."})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 10: Reports and Analytics (Headcount, Turnover, Costs, CSV Exports)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/reports/headcount")
    @admin_required
    def report_headcount():
        employees = db.read("employees") or []
        total = len(employees)
        by_dept = {}
        by_branch = {}
        by_type = {}
        for e in employees:
            d = e.get("department", "Unassigned")
            b = e.get("branch", "Main")
            t = e.get("employmentType", "Full-time")
            by_dept[d] = by_dept.get(d, 0) + 1
            by_branch[b] = by_branch.get(b, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1

        return jsonify({
            "totalHeadcount": total,
            "byDepartment": by_dept,
            "byBranch": by_branch,
            "byEmploymentType": by_type,
        })

    @app.get("/api/reports/turnover")
    @role_required("hr_manager")
    def report_turnover():
        employees = db.read("employees") or []
        offboarding = db.read("offboarding_records") or []
        active_count = len([e for e in employees if e.get("status", "active") == "active"])
        exits = len(offboarding)
        rate = round((exits / max(1, active_count + exits)) * 100, 1)

        return jsonify({
            "activeEmployees": active_count,
            "totalExits": exits,
            "turnoverRate": f"{rate}%",
            "retentionRate": f"{round(100 - rate, 1)}%",
        })

    @app.get("/api/reports/leave-utilization")
    @role_required("hr_manager")
    def report_leave_utilization():
        leaves = db.read("leave_requests") or []
        approved = [l for l in leaves if l.get("status") == "approved"]
        by_type = {}
        for l in approved:
            t = l.get("type", "Other")
            by_type[t] = by_type.get(t, 0) + (l.get("totalDays") or 1)
        return jsonify({
            "totalApprovedLeaveDays": sum(by_type.values()),
            "byType": by_type,
        })

    @app.get("/api/reports/analytics-summary")
    @admin_required
    def get_analytics_summary():
        employees = db.read("employees") or []
        admins = db.read("admins") or []
        total_employees = len(employees) or len([a for a in admins if a.get("status") == "active"])
        runs = db.read("payroll_runs") or []
        latest_run = next((r for r in sorted(runs, key=lambda x: x.get("monthYear", ""), reverse=True) if r.get("status") == "published"), None)
        monthly_cost = latest_run.get("totalGross", 0) if latest_run else sum(e.get("basicSalary", 50000) for e in employees)

        att = db.read("attendance") or []
        present = len([a for a in att if a.get("dayStatus") == "present"])
        late = len([a for a in att if (a.get("lateByMinutes") or 0) > 0])
        punctuality = round(((present - late) / max(1, present)) * 100, 1) if present else 95.0

        leaves = db.read("leave_requests") or []
        approved_leaves = len([l for l in leaves if l.get("status") == "approved"])
        pending_leaves = len([l for l in leaves if l.get("status") == "pending"])

        by_dept = {}
        by_branch = {}
        for e in employees:
            d = e.get("department", "Engineering")
            b = e.get("branch", "Warangal Headquarters")
            by_dept[d] = by_dept.get(d, 0) + 1
            by_branch[b] = by_branch.get(b, 0) + 1

        return jsonify({
            "totalEmployees": total_employees,
            "monthlyPayrollCost": monthly_cost,
            "punctualityRate": f"{punctuality}%",
            "leaveUtilization": approved_leaves,
            "pendingLeaves": pending_leaves,
            "byDepartment": by_dept,
            "byBranch": by_branch,
        })

    @app.get("/api/reports/export/<string:report_type>")
    @role_required("hr_manager")
    def export_report_csv(report_type):
        buf = io.StringIO()
        writer = csv.writer(buf)

        if report_type == "headcount":
            writer.writerow(["Department", "Branch", "Employee Code", "Name", "Designation", "Joining Date", "Status"])
            for e in db.read("employees") or []:
                writer.writerow([e.get("department"), e.get("branch"), e.get("employeeCode"), e.get("name"), e.get("designation"), e.get("joiningDate"), e.get("status")])
        elif report_type == "attendance":
            writer.writerow(["Date", "Employee Name", "Email", "Check In", "Check Out", "Worked Seconds", "Status"])
            for a in db.read("attendance") or []:
                writer.writerow([a.get("date"), a.get("adminName"), a.get("adminEmail"), a.get("checkIn"), a.get("checkOut"), a.get("workedSeconds"), a.get("dayStatus")])
        elif report_type == "payroll":
            writer.writerow(["Month", "Employee Code", "Name", "Department", "Basic", "HRA", "Allowances", "Gross", "PF", "Tax", "Net Pay"])
            for p in db.read("payslips") or []:
                writer.writerow([p.get("monthYear"), p.get("employeeCode"), p.get("employeeName"), p.get("department"), p.get("basic"), p.get("hra"), p.get("allowances"), p.get("grossEarnings"), p.get("pf"), p.get("tax"), p.get("netPay")])
        else:
            writer.writerow(["ID", "Type", "Status", "Created At"])

        output = buf.getvalue()
        return Response(output, mimetype="text/csv", headers={
            "Content-Disposition": f"attachment; filename=kyk_{report_type}_report_{_today_iso()}.csv"
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Module 11: Employee Lifecycle & Offboarding (Resignation, KT, Clearance)
    # ─────────────────────────────────────────────────────────────────────────

    @app.post("/api/lifecycle/resignation")
    @admin_required
    def submit_resignation():
        data = request.get_json(silent=True) or {}
        reason = clean(data.get("reason", ""), 500)
        notice_days = int(data.get("noticePeriodDays") or 30)

        admin = request.admin
        today_d = date.today()
        last_working = (today_d + timedelta(days=notice_days)).isoformat()

        row = db.insert("offboarding_records", {
            "employeeId": admin["id"],
            "employeeName": admin.get("name", "Staff"),
            "employeeEmail": admin.get("email", ""),
            "resignationDate": today_d.isoformat(),
            "noticePeriodDays": notice_days,
            "lastWorkingDate": last_working,
            "reason": reason,
            "status": "submitted",
            "ktStatus": False,
            "assetsReturned": False,
            "finalSettlementAmount": 0,
            "createdAt": _now_iso(),
        })

        # Notify HR
        db.insert("notifications", {
            "role": "hr_manager",
            "title": "Resignation Notice Submitted",
            "message": f"{admin.get('name')} submitted resignation. Notice period: {notice_days} days.",
            "category": "onboarding",
            "read": False,
            "createdAt": _now_iso(),
        })

        audit(admin, "resignation_submitted", f"Last working day: {last_working}")
        return jsonify(row), 201

    @app.get("/api/lifecycle/offboarding")
    @app.get("/api/offboarding/records")
    @role_required("hr_manager")
    def list_offboarding_records():
        rows = db.read("offboarding_records") or []
        rows.sort(key=lambda o: o.get("resignationDate", ""), reverse=True)
        return jsonify(rows)

    @app.post("/api/lifecycle/offboarding/<int:exit_id>/status")
    @role_required("hr_manager")
    def update_offboarding_status(exit_id):
        data = request.get_json(silent=True) or {}
        rec = db.find("offboarding_records", exit_id)
        if not rec:
            return error("Offboarding record not found.", 404)

        patch = {}
        if "status" in data:
            patch["status"] = clean(data["status"], 50)
        if "ktStatus" in data:
            patch["ktStatus"] = bool(data["ktStatus"])
        if "assetsReturned" in data:
            patch["assetsReturned"] = bool(data["assetsReturned"])
        if "exitInterviewNotes" in data:
            patch["exitInterviewNotes"] = clean(data["exitInterviewNotes"], 1000)

        updated = db.update("offboarding_records", exit_id, patch)
        audit(request.admin, "offboarding_updated", f"Record {exit_id}")
        return jsonify(updated)

    @app.post("/api/lifecycle/offboarding/<int:exit_id>/settle")
    @role_required("hr_manager")
    def settle_offboarding(exit_id):
        data = request.get_json(silent=True) or {}
        rec = db.find("offboarding_records", exit_id)
        if not rec:
            return error("Offboarding record not found.", 404)

        amount = int(data.get("finalSettlementAmount") or 0)
        db.update("offboarding_records", exit_id, {
            "status": "completed",
            "finalSettlementAmount": amount,
            "settledAt": _now_iso(),
            "settledBy": request.admin.get("name", "HR"),
        })

        # Deactivate employee record & user account
        emp_id = rec.get("employeeId")
        if emp_id:
            db.update("employees", emp_id, {"status": "resigned"})
        email = rec.get("employeeEmail", "").lower()
        for a in db.read("admins"):
            if a.get("email", "").lower() == email:
                db.update("admins", a["id"], {"status": "terminated"})
                break

        audit(request.admin, "offboarding_settled", f"Employee {rec.get('employeeName')} settled. INR {amount:,}")
        return jsonify({"message": "Offboarding settled and employee deactivated successfully."})

    # ─────────────────────────────────────────────────────────────────────────
    # Module 12: Administration and Audit (Company, Branches, Shifts, Backup)
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/admin/company")
    @app.get("/api/org/companies")
    @admin_required
    def get_company_profile():
        comps = db.read("companies") or []
        return jsonify(comps[0] if comps else {})

    @app.put("/api/admin/company")
    @app.put("/api/org/companies")
    @role_required("hr_manager")
    def update_company_profile():
        data = request.get_json(silent=True) or {}
        comps = db.read("companies") or []
        patch = {}
        for k in ["name", "registrationNo", "taxId", "email", "phone", "website", "timezone", "currency"]:
            if k in data:
                patch[k] = clean(data[k], 255)

        if comps:
            saved = db.update("companies", comps[0]["id"], patch)
        else:
            patch["code"] = "KYK-HQ"
            saved = db.insert("companies", patch)

        audit(request.admin, "company_updated", patch.get("name", ""))
        return jsonify(saved)

    @app.get("/api/admin/branches")
    @app.get("/api/org/branches")
    @admin_required
    def list_branches():
        return jsonify(db.read("branches") or [])

    @app.post("/api/admin/branches")
    @app.post("/api/org/branches")
    @role_required("hr_manager")
    def create_branch():
        data = request.get_json(silent=True) or {}
        name = clean(data.get("name", ""), 150)
        city = clean(data.get("city", ""), 100)
        code = clean(data.get("code", ""), 50).upper() or f"BR-{len(db.read('branches') or []) + 1:02d}"
        if not name or not city:
            return error("Branch name and city are required.")

        branch = db.insert("branches", {
            "name": name,
            "code": code,
            "city": city,
            "state": clean(data.get("state", ""), 100),
            "address": clean(data.get("address", ""), 255),
            "phone": clean(data.get("phone", ""), 50),
            "isHeadquarters": bool(data.get("isHeadquarters", False)),
        })
        audit(request.admin, "branch_created", name)
        return jsonify(branch), 201

    @app.get("/api/admin/departments")
    @app.get("/api/org/departments")
    @admin_required
    def list_departments():
        return jsonify(db.read("departments") or [])

    @app.post("/api/admin/departments")
    @app.post("/api/org/departments")
    @role_required("hr_manager")
    def create_department():
        data = request.get_json(silent=True) or {}
        name = clean(data.get("name", ""), 120)
        code = clean(data.get("code", ""), 50).upper() or f"D-{len(db.read('departments') or []) + 1:02d}"
        if not name:
            return error("Department name is required.")

        dept = db.insert("departments", {
            "name": name,
            "code": code,
            "headName": clean(data.get("headName", ""), 150),
            "description": clean(data.get("description", ""), 300),
        })
        audit(request.admin, "department_created", name)
        return jsonify(dept), 201

    @app.get("/api/admin/designations")
    @app.get("/api/org/designations")
    @admin_required
    def list_designations():
        return jsonify(db.read("designations") or [])

    @app.post("/api/admin/designations")
    @app.post("/api/org/designations")
    @role_required("hr_manager")
    def create_designation():
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", ""), 120)
        dept = clean(data.get("department", "Software & Web Services"), 120)
        if not title:
            return error("Designation title is required.")

        desig = db.insert("designations", {
            "title": title,
            "department": dept,
            "level": clean(data.get("level", "Mid-level"), 50),
            "description": clean(data.get("description", ""), 300),
        })
        audit(request.admin, "designation_created", title)
        return jsonify(desig), 201

    @app.get("/api/admin/shifts")
    @app.get("/api/org/shifts")
    @admin_required
    def list_shifts():
        return jsonify(db.read("shifts") or [])

    @app.post("/api/admin/shifts")
    @app.post("/api/org/shifts")
    @role_required("hr_manager")
    def create_shift():
        data = request.get_json(silent=True) or {}
        name = clean(data.get("name", ""), 100)
        start = clean(data.get("startTime", "09:30"), 10)
        end = clean(data.get("endTime", "18:15"), 10)
        if not name:
            return error("Shift name is required.")

        sh = db.insert("shifts", {
            "name": name,
            "startTime": start,
            "endTime": end,
            "lateGraceMinutes": int(data.get("lateGraceMinutes") or 15),
            "earlyGraceMinutes": int(data.get("earlyGraceMinutes") or 15),
            "workingDays": clean(data.get("workingDays", "0,1,2,3,4"), 50),
        })
        audit(request.admin, "shift_created", name)
        return jsonify(sh), 201

    @app.get("/api/admin/backup/export")
    @app.get("/api/admin/export-backup")
    @role_required("hr_manager")
    def export_database_backup():
        collections = [
            "companies", "branches", "departments", "designations",
            "employees", "employment_history", "admins", "shifts",
            "holidays", "leave_types", "leave_balances", "leave_requests",
            "salary_structures", "payroll_runs", "payslips", "onboarding_tasks",
            "performance_cycles", "performance_goals", "performance_reviews",
            "timesheets", "documents", "announcements", "notifications",
            "offboarding_records", "attendance", "audit_log"
        ]
        backup = {}
        for c in collections:
            backup[c] = db.read(c) or []

        audit(request.admin, "system_backup_exported", f"{len(collections)} collections")
        return Response(
            json.dumps(backup, indent=2, default=str),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename=kyk_hrms_backup_{_today_iso()}.json"}
        )

    @app.get("/api/admin/system/health")
    @role_required("hr_manager")
    def system_health_status():
        emp_count = len(db.read("employees") or [])
        user_count = len(db.read("admins") or [])
        att_count = len(db.read("attendance") or [])
        sessions = len(db.read("sessions") or [])

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "employeesActive": emp_count,
            "userAccounts": user_count,
            "attendancePunches": att_count,
            "activeSessions": sessions,
            "serverTime": _now_iso(),
            "timezone": str(COMPANY_TZ),
        })

    print("Registered comprehensive HRMS routes (Modules 1 to 12).")
