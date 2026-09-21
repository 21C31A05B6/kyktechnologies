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
