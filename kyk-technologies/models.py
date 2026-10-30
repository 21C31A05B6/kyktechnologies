"""models.py — SQLAlchemy ORM models for separate role tables.

Defines dedicated database models for:
- User (users)
- Admin (admins)
- Employee (employees)
- HRManager (hr_managers)
- TeamLead (team_leads)
- Recruiter (recruiters)
- Client (clients)
- ContentManager (content_managers)
"""

from datetime import datetime, timezone, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(150), nullable=False)
    role = Column(String(50), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(50), default="active", nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    # Relationships to specific role profiles
    admin_profile = relationship("Admin", back_populates="user", uselist=False, cascade="all, delete-orphan")
    employee_profile = relationship("Employee", back_populates="user", uselist=False, cascade="all, delete-orphan")
    hr_profile = relationship("HRManager", back_populates="user", uselist=False, cascade="all, delete-orphan")
    team_lead_profile = relationship("TeamLead", back_populates="user", uselist=False, cascade="all, delete-orphan")
    recruiter_profile = relationship("Recruiter", back_populates="user", uselist=False, cascade="all, delete-orphan")
    client_profile = relationship("Client", back_populates="user", uselist=False, cascade="all, delete-orphan")
    content_manager_profile = relationship("ContentManager", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "phone": self.phone,
            "status": self.status,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "lastLoginIp": self.last_login_ip,
            "loginCount": self.login_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_super_admin = Column(Boolean, default=True, nullable=False)
    department = Column(String(100), default="Executive")
    access_level = Column(String(50), default="all")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="admin_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "isSuperAdmin": self.is_super_admin,
            "department": self.department,
            "accessLevel": self.access_level,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "lastLoginIp": self.last_login_ip,
            "loginCount": self.login_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), default="Software & Web Services")
    designation = Column(String(100), default="Software Engineer")
    employment_type = Column(String(50), default="Full-time")
    joining_date = Column(Date, default=date.today)
    attendance_eligible = Column(Boolean, default=True, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="employee_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "employeeCode": self.employee_code,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "designation": self.designation,
            "employmentType": self.employment_type,
            "joiningDate": self.joining_date.isoformat() if self.joining_date else None,
            "attendanceEligible": self.attendance_eligible,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class HRManager(Base):
    __tablename__ = "hr_managers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), default="Human Resources")
    office_location = Column(String(100), default="Warangal, IN")
    can_manage_attendance = Column(Boolean, default=True, nullable=False)
    can_manage_payroll = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="hr_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "officeLocation": self.office_location,
            "canManageAttendance": self.can_manage_attendance,
            "canManagePayroll": self.can_manage_payroll,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class TeamLead(Base):
    __tablename__ = "team_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), default="Software & Web Services")
    team_name = Column(String(100), default="Core Engineering")
    max_team_size = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="team_lead_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "teamName": self.team_name,
            "maxTeamSize": self.max_team_size,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Recruiter(Base):
    __tablename__ = "recruiters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    specialization = Column(String(100), default="Technical & Global Sourcing")
    assigned_region = Column(String(100), default="Global")
    target_hires_per_quarter = Column(Integer, default=15)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="recruiter_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "specialization": self.specialization,
            "assignedRegion": self.assigned_region,
            "targetHiresPerQuarter": self.target_hires_per_quarter,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    client_name = Column(String(150), nullable=False)
    company_name = Column(String(200), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    industry = Column(String(100), default="Technology")
    billing_address = Column(Text, nullable=True)
    contract_status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="client_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "clientName": self.client_name,
            "companyName": self.company_name,
            "email": self.email,
            "phone": self.phone,
            "industry": self.industry,
            "billingAddress": self.billing_address,
            "contractStatus": self.contract_status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class ContentManager(Base):
    __tablename__ = "content_managers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), default="Marketing & Content")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    user = relationship("User", back_populates="content_manager_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    department = Column(String(120), nullable=False, index=True)
    location = Column(String(120), nullable=False)
    type = Column(String(50), default="Full-time")
    level = Column(String(50), default="Mid-level")
    description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "department": self.department,
            "location": self.location,
            "type": self.type,
            "level": self.level,
            "description": self.description,
            "requirements": self.requirements or [],
            "active": self.active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=True, index=True)
    job_title = Column(String(200), nullable=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(50), default="applied", index=True)
    notes = Column(Text, nullable=True)
    resume_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "jobId": self.job_id,
            "jobTitle": self.job_title,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "notes": self.notes,
            "resumeFilename": self.resume_filename,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class AttendanceRecord(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    user_name = Column(String(150), nullable=True)
    user_email = Column(String(255), nullable=True, index=True)
    user_role = Column(String(50), nullable=True)
    date = Column(String(20), nullable=False, index=True)
    check_in = Column(String(50), nullable=True)
    check_out = Column(String(50), nullable=True)
    worked_seconds = Column(Integer, default=0)
    day_status = Column(String(50), default="present")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "adminId": self.user_id,
            "adminName": self.user_name,
            "adminEmail": self.user_email,
            "adminRole": self.user_role,
            "date": self.date,
            "checkIn": self.check_in,
            "checkOut": self.check_out,
            "workedSeconds": self.worked_seconds,
            "dayStatus": self.day_status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=True)
    admin_email = Column(String(255), nullable=True, index=True)
    admin_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    detail = Column(Text, nullable=True)
    ip = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "adminId": self.admin_id,
            "adminEmail": self.admin_email,
            "adminRole": self.admin_role,
            "action": self.action,
            "detail": self.detail,
            "ip": self.ip,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(100), unique=True, nullable=False, index=True)
    owner_type = Column(String(50), nullable=False)
    owner_id = Column(Integer, nullable=False, index=True)
    ip = Column(String(50), nullable=True)
    ua = Column(String(255), nullable=True)
    exp = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "jti": self.jti,
            "owner_type": self.owner_type,
            "owner_id": self.owner_id,
            "ip": self.ip,
            "ua": self.ua,
            "exp": self.exp,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ── HRMS Core Normalized Models ──────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    registration_no = Column(String(100), nullable=True)
    tax_id = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    timezone = Column(String(100), default="Asia/Kolkata")
    currency = Column(String(10), default="INR")
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "registrationNo": self.registration_no,
            "taxId": self.tax_id,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "timezone": self.timezone,
            "currency": self.currency,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(150), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    country = Column(String(100), default="India")
    phone = Column(String(50), nullable=True)
    is_headquarters = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "companyId": self.company_id,
            "name": self.name,
            "code": self.code,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "phone": self.phone,
            "isHeadquarters": self.is_headquarters,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    head_name = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "headName": self.head_name,
            "description": self.description,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Designation(Base):
    __tablename__ = "designations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(120), nullable=False)
    department = Column(String(120), nullable=False)
    level = Column(String(50), default="Mid-level")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "department": self.department,
            "level": self.level,
            "description": self.description,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class EmploymentHistory(Base):
    __tablename__ = "employment_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # onboarding, promotion, transfer, salary_revision, resignation
    from_value = Column(String(200), nullable=True)
    to_value = Column(String(200), nullable=True)
    effective_date = Column(Date, nullable=False)
    remarks = Column(Text, nullable=True)
    recorded_by = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "eventType": self.event_type,
            "fromValue": self.from_value,
            "toValue": self.to_value,
            "effectiveDate": self.effective_date.isoformat() if self.effective_date else None,
            "remarks": self.remarks,
            "recordedBy": self.recorded_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    late_grace_minutes = Column(Integer, default=15)
    early_grace_minutes = Column(Integer, default=15)
    working_days = Column(String(50), default="0,1,2,3,4")  # Mon-Fri
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "lateGraceMinutes": self.late_grace_minutes,
            "earlyGraceMinutes": self.early_grace_minutes,
            "workingDays": self.working_days,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Holiday(Base):
    __tablename__ = "holiday_calendars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    date = Column(Date, nullable=False, index=True)
    optional = Column(Boolean, default=False)
    branch = Column(String(100), default="All")
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "date": self.date.isoformat() if self.date else None,
            "optional": self.optional,
            "branch": self.branch,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class LeaveType(Base):
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    quota_per_year = Column(Integer, default=12)
    carry_forward_max = Column(Integer, default=5)
    paid = Column(Boolean, default=True)
    description = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "quotaPerYear": self.quota_per_year,
            "carryForwardMax": self.carry_forward_max,
            "paid": self.paid,
            "description": self.description,
        }


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    balances = Column(JSON, nullable=False)  # { "Casual Leave": {"quota": 12, "used": 2, "available": 10} }
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "year": self.year,
            "balances": self.balances or {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    employee_email = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    total_days = Column(Integer, default=1)
    reason = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # pending, approved, rejected, cancelled
    manager_id = Column(Integer, nullable=True)
    manager_comment = Column(Text, nullable=True)
    decided_by = Column(String(150), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "adminId": self.employee_id,
            "employeeId": self.employee_id,
            "adminName": self.employee_name,
            "adminEmail": self.employee_email,
            "type": self.type,
            "fromDate": self.from_date.isoformat() if self.from_date else None,
            "toDate": self.to_date.isoformat() if self.to_date else None,
            "totalDays": self.total_days,
            "reason": self.reason,
            "status": self.status,
            "managerComment": self.manager_comment,
            "decidedBy": self.decided_by,
            "decidedAt": self.decided_at.isoformat() if self.decided_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, unique=True, nullable=False, index=True)
    basic_salary = Column(Integer, default=40000)
    hra = Column(Integer, default=16000)
    special_allowance = Column(Integer, default=10000)
    conveyance = Column(Integer, default=3000)
    pf_deduction = Column(Integer, default=1800)
    tax_deduction = Column(Integer, default=2500)
    gross_salary = Column(Integer, default=69000)
    net_salary = Column(Integer, default=64700)
    effective_from = Column(Date, default=date.today)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "basicSalary": self.basic_salary,
            "hra": self.hra,
            "specialAllowance": self.special_allowance,
            "conveyance": self.conveyance,
            "pfDeduction": self.pf_deduction,
            "taxDeduction": self.tax_deduction,
            "grossSalary": self.gross_salary,
            "netSalary": self.net_salary,
            "effectiveFrom": self.effective_from.isoformat() if self.effective_from else None,
        }


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month_year = Column(String(20), unique=True, nullable=False)  # '2026-10'
    status = Column(String(50), default="draft")  # draft, approved, published
    total_gross = Column(Integer, default=0)
    total_deductions = Column(Integer, default=0)
    total_net = Column(Integer, default=0)
    employee_count = Column(Integer, default=0)
    processed_by = Column(String(150), nullable=True)
    processed_at = Column(DateTime(timezone=True), default=_now_utc)
    published_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "monthYear": self.month_year,
            "status": self.status,
            "totalGross": self.total_gross,
            "totalDeductions": self.total_deductions,
            "totalNet": self.total_net,
            "employeeCount": self.employee_count,
            "processedBy": self.processed_by,
            "processedAt": self.processed_at.isoformat() if self.processed_at else None,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
        }


class Payslip(Base):
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payroll_run_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_code = Column(String(50), nullable=False)
    employee_name = Column(String(150), nullable=False)
    employee_email = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)
    month_year = Column(String(20), nullable=False, index=True)
    basic = Column(Integer, default=0)
    hra = Column(Integer, default=0)
    allowances = Column(Integer, default=0)
    bonus = Column(Integer, default=0)
    gross_earnings = Column(Integer, default=0)
    pf = Column(Integer, default=0)
    tax = Column(Integer, default=0)
    deductions = Column(Integer, default=0)
    net_pay = Column(Integer, default=0)
    status = Column(String(50), default="published")  # draft, published
    published_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "payrollRunId": self.payroll_run_id,
            "employeeId": self.employee_id,
            "employeeCode": self.employee_code,
            "employeeName": self.employee_name,
            "employeeEmail": self.employee_email,
            "department": self.department,
            "designation": self.designation,
            "monthYear": self.month_year,
            "basic": self.basic,
            "hra": self.hra,
            "allowances": self.allowances,
            "bonus": self.bonus,
            "grossEarnings": self.gross_earnings,
            "pf": self.pf,
            "tax": self.tax,
            "deductions": self.deductions,
            "netPay": self.net_pay,
            "status": self.status,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
        }


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default="HR")  # HR, IT, Manager, Employee
    assigned_to = Column(String(150), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(50), default="pending")  # pending, completed
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "title": self.title,
            "category": self.category,
            "assignedTo": self.assigned_to,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    period = Column(String(50), nullable=False)  # e.g. Q4 2026
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(50), default="active")  # active, completed

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "period": self.period,
            "startDate": self.start_date.isoformat() if self.start_date else None,
            "endDate": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
        }


class PerformanceGoal(Base):
    __tablename__ = "performance_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    manager_id = Column(Integer, nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    kpi = Column(String(150), nullable=True)
    target_value = Column(String(100), nullable=True)
    progress = Column(Integer, default=0)  # 0-100%
    due_date = Column(Date, nullable=True)
    status = Column(String(50), default="in_progress")  # not_started, in_progress, completed

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "managerId": self.manager_id,
            "title": self.title,
            "description": self.description,
            "kpi": self.kpi,
            "targetValue": self.target_value,
            "progress": self.progress,
            "dueDate": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
        }


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(Integer, nullable=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    reviewer_id = Column(Integer, nullable=True)
    reviewer_name = Column(String(150), nullable=True)
    self_rating = Column(Integer, default=4)  # 1-5
    self_assessment = Column(Text, nullable=True)
    manager_rating = Column(Integer, default=4)
    manager_feedback = Column(Text, nullable=True)
    status = Column(String(50), default="submitted")  # draft, submitted, completed
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "cycleId": self.cycle_id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "reviewerId": self.reviewer_id,
            "reviewerName": self.reviewer_name,
            "selfRating": self.self_rating,
            "selfAssessment": self.self_assessment,
            "managerRating": self.manager_rating,
            "managerFeedback": self.manager_feedback,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Timesheet(Base):
    __tablename__ = "timesheets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    week_start_date = Column(Date, nullable=False)
    project_name = Column(String(150), nullable=False)
    hours_breakdown = Column(JSON, nullable=False)  # {"mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8}
    total_hours = Column(Integer, default=40)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="submitted")  # submitted, approved, rejected
    approved_by = Column(String(150), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "weekStartDate": self.week_start_date.isoformat() if self.week_start_date else None,
            "projectName": self.project_name,
            "hoursBreakdown": self.hours_breakdown or {},
            "totalHours": self.total_hours,
            "notes": self.notes,
            "status": self.status,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at.isoformat() if self.approved_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=True, index=True)
    employee_name = Column(String(150), nullable=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default="policy")  # id_proof, offer_letter, contract, certificate, policy, other
    file_url = Column(String(255), nullable=False)
    file_size = Column(String(50), default="1.2 MB")
    expiry_date = Column(Date, nullable=True)
    is_confidential = Column(Boolean, default=False)
    is_company_policy = Column(Boolean, default=False)
    acknowledged_by = Column(JSON, default=list)  # list of user ids who acknowledged
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "title": self.title,
            "category": self.category,
            "fileUrl": self.file_url,
            "fileSize": self.file_size,
            "expiryDate": self.expiry_date.isoformat() if self.expiry_date else None,
            "isConfidential": self.is_confidential,
            "isCompanyPolicy": self.is_company_policy,
            "acknowledgedBy": self.acknowledged_by or [],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    role = Column(String(50), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(50), default="info")  # leave, attendance, payroll, onboarding, performance, announcement
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "userEmail": self.user_email,
            "role": self.role,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "read": self.read,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    target_department = Column(String(100), default="All")
    author_name = Column(String(150), default="HR Department")
    pinned = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "targetDepartment": self.target_department,
            "authorName": self.author_name,
            "pinned": self.pinned,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class OffboardingRecord(Base):
    __tablename__ = "offboarding_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, nullable=False, index=True)
    employee_name = Column(String(150), nullable=False)
    employee_email = Column(String(255), nullable=False)
    resignation_date = Column(Date, nullable=False)
    notice_period_days = Column(Integer, default=30)
    last_working_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(50), default="submitted")  # submitted, approved, clearance_in_progress, completed
    kt_status = Column(Boolean, default=False)
    assets_returned = Column(Boolean, default=False)
    final_settlement_amount = Column(Integer, default=0)
    exit_interview_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee_name,
            "employeeEmail": self.employee_email,
            "resignationDate": self.resignation_date.isoformat() if self.resignation_date else None,
            "noticePeriodDays": self.notice_period_days,
            "lastWorkingDate": self.last_working_date.isoformat() if self.last_working_date else None,
            "reason": self.reason,
            "status": self.status,
            "ktStatus": self.kt_status,
            "assetsReturned": self.assets_returned,
            "finalSettlementAmount": self.final_settlement_amount,
            "exitInterviewNotes": self.exit_interview_notes,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ── Real-Time Role-Based Enterprise Communication & Meeting Models ───────────

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), default="direct", nullable=False, index=True)  # direct, group, department, announcement, project
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(255), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    project_name = Column(String(100), nullable=True, index=True)
    is_announcement = Column(Boolean, default=False, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc, index=True)

    members = relationship("ChatConversationMember", back_populates="conversation", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "avatarUrl": self.avatar_url,
            "createdById": self.created_by_id,
            "department": self.department,
            "projectName": self.project_name,
            "isAnnouncement": self.is_announcement,
            "isArchived": self.is_archived,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatConversationMember(Base):
    __tablename__ = "chat_conversation_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="member", nullable=False)  # owner, admin, member
    is_muted = Column(Boolean, default=False, nullable=False)
    last_read_message_id = Column(Integer, nullable=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), default=_now_utc)
    left_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conv_user"),
    )

    conversation = relationship("ChatConversation", back_populates="members")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "conversationId": self.conversation_id,
            "userId": self.user_id,
            "role": self.role,
            "isMuted": self.is_muted,
            "lastReadMessageId": self.last_read_message_id,
            "lastReadAt": self.last_read_at.isoformat() if self.last_read_at else None,
            "joinedAt": self.joined_at.isoformat() if self.joined_at else None,
            "leftAt": self.left_at.isoformat() if self.left_at else None,
        }


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_name = Column(String(150), nullable=False)
    sender_role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text", nullable=False)  # text, file, system
    reply_to_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    is_edited = Column(Boolean, default=False, nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_pinned = Column(Boolean, default=False, nullable=False, index=True)
    pinned_by_id = Column(Integer, nullable=True)
    pinned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    conversation = relationship("ChatConversation", back_populates="messages")
    sender = relationship("User")
    reply_to = relationship("ChatMessage", remote_side=[id], foreign_keys=[reply_to_id])
    attachments = relationship("ChatMessageAttachment", back_populates="message", cascade="all, delete-orphan")
    reactions = relationship("ChatMessageReaction", back_populates="message", cascade="all, delete-orphan")
    read_receipts = relationship("ChatMessageReadReceipt", back_populates="message", cascade="all, delete-orphan")

    def to_dict(self):
        reply_dict = None
        try:
            if self.reply_to:
                reply_dict = {
                    "id": self.reply_to.id,
                    "senderName": getattr(self.reply_to, "sender_name", "User"),
                    "content": self.reply_to.content if not getattr(self.reply_to, "is_deleted", False) else "This message was deleted.",
                }
        except Exception:
            reply_dict = None

        att_list = []
        try:
            if self.attachments:
                att_list = [a.to_dict() for a in self.attachments]
        except Exception:
            att_list = []

        rxn_list = []
        try:
            if self.reactions:
                rxn_list = [r.to_dict() for r in self.reactions]
        except Exception:
            rxn_list = []

        return {
            "id": self.id,
            "conversationId": self.conversation_id,
            "senderId": self.sender_id,
            "senderName": self.sender_name,
            "senderRole": self.sender_role,
            "content": self.content if not self.is_deleted else "This message was deleted.",
            "messageType": self.message_type,
            "replyToId": self.reply_to_id,
            "replyTo": reply_dict,
            "isEdited": self.is_edited,
            "editedAt": self.edited_at.isoformat() if self.edited_at else None,
            "isDeleted": self.is_deleted,
            "deletedAt": self.deleted_at.isoformat() if self.deleted_at else None,
            "isPinned": self.is_pinned,
            "pinnedById": self.pinned_by_id,
            "pinnedAt": self.pinned_at.isoformat() if self.pinned_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "attachments": att_list,
            "reactions": rxn_list,
        }


class ChatMessageAttachment(Base):
    __tablename__ = "chat_message_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_url = Column(String(255), nullable=False)
    file_type = Column(String(100), default="application/octet-stream")
    file_size = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    message = relationship("ChatMessage", back_populates="attachments")

    def to_dict(self):
        return {
            "id": self.id,
            "messageId": self.message_id,
            "filename": self.filename,
            "fileUrl": self.file_url,
            "fileType": self.file_type,
            "fileSize": self.file_size,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class ChatMessageReaction(Base):
    __tablename__ = "chat_message_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_name = Column(String(150), nullable=False)
    emoji = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_msg_user_emoji"),
    )

    message = relationship("ChatMessage", back_populates="reactions")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "messageId": self.message_id,
            "userId": self.user_id,
            "userName": self.user_name,
            "emoji": self.emoji,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class ChatMessageReadReceipt(Base):
    __tablename__ = "chat_message_read_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), default=_now_utc)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_msg_user_read"),
    )

    message = relationship("ChatMessage", back_populates="read_receipts")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "messageId": self.message_id,
            "userId": self.user_id,
            "readAt": self.read_at.isoformat() if self.read_at else None,
        }


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    host_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    host_name = Column(String(150), nullable=False)
    status = Column(String(50), default="scheduled", nullable=False, index=True)  # scheduled, live, completed, cancelled
    meeting_type = Column(String(50), default="scheduled", nullable=False)  # instant, scheduled
    scheduled_start = Column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    target_department = Column(String(100), nullable=True)
    target_role = Column(String(50), nullable=True)
    is_recorded = Column(Boolean, default=False)
    recording_url = Column(String(255), nullable=True)
    recording_status = Column(String(50), default="none")  # none, recording, saved
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    host = relationship("User")
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    chat_messages = relationship("MeetingChatMessage", back_populates="meeting", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "meetingCode": self.meeting_code,
            "title": self.title,
            "description": self.description,
            "hostId": self.host_id,
            "hostName": self.host_name,
            "status": self.status,
            "meetingType": self.meeting_type,
            "scheduledStart": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "scheduledEnd": self.scheduled_end.isoformat() if self.scheduled_end else None,
            "actualStart": self.actual_start.isoformat() if self.actual_start else None,
            "actualEnd": self.actual_end.isoformat() if self.actual_end else None,
            "targetDepartment": self.target_department,
            "targetRole": self.target_role,
            "isRecorded": self.is_recorded,
            "recordingUrl": self.recording_url,
            "recordingStatus": self.recording_status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "participantCount": len(self.participants) if self.participants else 0,
        }


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_name = Column(String(150), nullable=False)
    user_email = Column(String(255), nullable=False)
    user_role = Column(String(50), nullable=False)
    invitation_status = Column(String(50), default="invited", nullable=False)  # invited, accepted, declined
    attendance_status = Column(String(50), default="absent", nullable=False)  # absent, joined, left
    joined_at = Column(DateTime(timezone=True), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meet_user"),
    )

    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "meetingId": self.meeting_id,
            "userId": self.user_id,
            "userName": self.user_name,
            "userEmail": self.user_email,
            "userRole": self.user_role,
            "invitationStatus": self.invitation_status,
            "attendanceStatus": self.attendance_status,
            "joinedAt": self.joined_at.isoformat() if self.joined_at else None,
            "leftAt": self.left_at.isoformat() if self.left_at else None,
            "durationSeconds": self.duration_seconds,
        }


class MeetingChatMessage(Base):
    __tablename__ = "meeting_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_name = Column(String(150), nullable=False)
    sender_role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)

    meeting = relationship("Meeting", back_populates="chat_messages")
    sender = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "meetingId": self.meeting_id,
            "senderId": self.sender_id,
            "senderName": self.sender_name,
            "senderRole": self.sender_role,
            "content": self.content,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }

