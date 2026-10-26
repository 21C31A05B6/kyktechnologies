"""chat_api.py — Enterprise Real-Time Role-Based Communication & Video Meeting Engine.

Provides:
- One-to-one individual messaging
- Group messaging with owners, admins, and members
- Role-based and department-based communication
- Super Admin & HR company announcements (read-only for non-admins)
- Message reactions, pinning, editing, deletion, replies, read receipts
- File attachments with validation and authorized serving
- Full-text search within authorized conversations
- WebRTC video & audio meeting coordination (mesh signaling, camera/mic/screen share)
- Meeting scheduling, calendar invitations, RSVP, live attendance tracking
- Real-time Socket.IO events for presence, typing, messages, and calls
"""

import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import jsonify, request, send_from_directory, current_app
from flask_socketio import emit, join_room, leave_room, rooms, disconnect
from sqlalchemy import select, and_, or_, func, desc
from werkzeug.utils import secure_filename

import db
from models import (
    Base,
    User,
    Admin,
    Employee,
    HRManager,
    TeamLead,
    Recruiter,
    Client,
    ContentManager,
    ChatConversation,
    ChatConversationMember,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageReaction,
    ChatMessageReadReceipt,
    Meeting,
    MeetingParticipant,
    MeetingChatMessage,
)
from security import read_token

# ── Global In-Memory State for Real-Time Presence & Meetings ─────────────────
# online_users: user_id -> { "sids": set(), "user": dict, "status": "online", "last_seen": iso }
_online_users = {}
# sid_to_user: sid -> user_id
_sid_to_user = {}
# sid_to_jti: sid -> jti
_sid_to_jti = {}
# sid_to_meeting: sid -> meeting_code
_sid_to_meeting = {}
# active_meeting_peers: meeting_code -> set of sids
_meeting_rooms = {}

_session_valid_callback = None
_active_socketio = None


def set_session_validator(fn):
    global _session_valid_callback
    _session_valid_callback = fn


def set_socketio(sio):
    global _active_socketio
    _active_socketio = sio


def disconnect_sockets_for_jti(jti):
    if not jti or not _active_socketio:
        return
    targets = [sid for sid, s_jti in _sid_to_jti.items() if s_jti == jti]
    for sid in targets:
        try:
            _active_socketio.disconnect(sid)
        except Exception:
            pass


def disconnect_sockets_for_user(user_id):
    if not user_id or not _active_socketio:
        return
    targets = [sid for sid, uid in _sid_to_user.items() if uid == user_id]
    for sid in targets:
        try:
            _active_socketio.disconnect(sid)
        except Exception:
            pass

ALLOWED_CHAT_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".zip", ".tar", ".gz", ".mp3", ".wav", ".mp4", ".webm"
}
MAX_CHAT_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def _now_utc():
    return datetime.now(timezone.utc)


def _get_session():
    """Retrieve SQLAlchemy session from db_sql."""
    from db_sql import _Session
    return _Session()


DISALLOWED_CHAT_ROLES = {"user", "viewer"}


def _norm_role(role):
    if role == "admin": return "super_admin"
    if role == "hr": return "hr_manager"
    if role == "manager": return "team_lead"
    return role or "viewer"


def is_chat_allowed_role(role):
    r = _norm_role(role).lower().strip()
    return r not in DISALLOWED_CHAT_ROLES


def _user_from_token(token):
    if not token:
        return None
    payload = read_token(token)
    if not payload:
        return None
    jti = payload.get("jti", "")
    if _session_valid_callback and not _session_valid_callback(jti):
        return None
    admin_id = payload.get("adminId") or payload.get("id") or payload.get("userId")
    if not admin_id:
        return None
    user_row = db.find("admins", admin_id) or db.find("users", admin_id)
    if not user_row:
        # Fallback query directly to User model
        try:
            with _get_session() as s:
                u = s.get(User, int(admin_id))
                if u:
                    user_row = u.to_dict()
        except Exception:
            pass
    if user_row and user_row.get("status") in {"suspended", "inactive", "terminated", "chat_disabled"}:
        return None
    if user_row:
        user_row["_jti"] = jti
    return user_row


def register_chat_routes(app, socketio, deps):
    set_socketio(socketio)
    if "_session_valid" in deps:
        set_session_validator(deps["_session_valid"])
    db_ref = deps["db"]
    clean = deps.get("clean", lambda s, maxlen=500: str(s or "")[:maxlen].strip())
    error = deps.get("error", lambda msg, status=400: (jsonify({"error": msg}), status))
    audit = deps.get("audit", lambda admin, action, detail="": None)
    current_admin = deps["current_admin"]

    upload_chat_dir = os.path.join(app.root_path, "uploads", "chat")
    os.makedirs(upload_chat_dir, exist_ok=True)

    def chat_auth_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else request.args.get("token", "")
            admin = current_admin() or _user_from_token(token)
            if not admin:
                return jsonify({"error": "Unauthorized or session expired.", "kicked": True}), 401
            if admin.get("status") in {"suspended", "inactive", "terminated", "chat_disabled"}:
                return error("Your communication access has been suspended. Please contact HR or IT.", 403)
            # Enforce role permission: viewers and general users are forbidden from chat and meetings
            role = _norm_role(admin.get("role"))
            if role in DISALLOWED_CHAT_ROLES:
                return error("Access denied: General users and viewers do not have permissions for chat and meetings.", 403)
            request.admin = admin
            return view(*args, **kwargs)
        return wrapper

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-Provision Default Company Channels
    # ─────────────────────────────────────────────────────────────────────────
    def init_default_channels():
        try:
            with _get_session() as session:
                users = session.scalars(
                    select(User).where(and_(User.status == "active", ~User.role.in_(DISALLOWED_CHAT_ROLES)))
                ).all()
                if not users:
                    return

                # Purge any legacy memberships for viewers or general users
                disallowed_user_ids = set(session.scalars(select(User.id).where(User.role.in_(DISALLOWED_CHAT_ROLES))).all())
                if disallowed_user_ids:
                    session.query(ChatConversationMember).filter(ChatConversationMember.user_id.in_(disallowed_user_ids)).delete(synchronize_session=False)
                    session.commit()

                super_admin = next((u for u in users if u.role in ("super_admin", "admin")), users[0])

                default_channels = [
                    {
                        "type": "announcement",
                        "title": "Company Announcements",
                        "description": "Official company-wide announcements from Leadership and HR. Read-only for employees.",
                        "is_announcement": True,
                        "department": "All",
                        "auto_join_all": True,
                    },
                    {
                        "type": "department",
                        "title": "General Discussion",
                        "description": "General open watercooler channel for all KYK Technologies team members.",
                        "is_announcement": False,
                        "department": "All",
                        "auto_join_all": True,
                    },
                    {
                        "type": "department",
                        "title": "Software & Web Services",
                        "description": "Engineering, frontend, backend, DevOps, and cloud infrastructure discussions.",
                        "is_announcement": False,
                        "department": "Software & Web Services",
                        "auto_roles": {"super_admin", "admin", "hr_manager", "team_lead", "employee"},
                    },
                    {
                        "type": "department",
                        "title": "AI, AGI & ASI Applications",
                        "description": "Applied AI engineering, model training, neural architectures, and intelligent systems.",
                        "is_announcement": False,
                        "department": "AI, AGI, ASI Applications",
                        "auto_roles": {"super_admin", "admin", "hr_manager", "team_lead", "employee"},
                    },
                    {
                        "type": "department",
                        "title": "Global Recruitment Hub",
                        "description": "Candidate pipelines, global talent sourcing, interviews, and offer management.",
                        "is_announcement": False,
                        "department": "Global Recruitment",
                        "auto_roles": {"super_admin", "admin", "hr_manager", "recruiter"},
                    },
                    {
                        "type": "group",
                        "title": "Leadership & Strategy",
                        "description": "Confidential management discussions, company strategy, and quarterly roadmap.",
                        "is_announcement": False,
                        "department": "Executive",
                        "auto_roles": {"super_admin", "admin", "hr_manager", "team_lead"},
                    },
                ]

                for ch in default_channels:
                    existing = session.scalars(
                        select(ChatConversation).where(
                            and_(
                                ChatConversation.title == ch["title"],
                                ChatConversation.is_archived.is_(False),
                            )
                        )
                    ).first()

                    if not existing:
                        conv = ChatConversation(
                            type=ch["type"],
                            title=ch["title"],
                            description=ch["description"],
                            is_announcement=ch["is_announcement"],
                            department=ch.get("department"),
                            created_by_id=super_admin.id,
                            created_at=_now_utc(),
                            updated_at=_now_utc(),
                        )
                        session.add(conv)
                        session.flush()

                        # Add members
                        for u in users:
                            role_norm = _norm_role(u.role)
                            should_add = False
                            if ch.get("auto_join_all"):
                                should_add = True
                            elif ch.get("auto_roles") and (u.role in ch["auto_roles"] or role_norm in ch["auto_roles"]):
                                should_add = True

                            if should_add:
                                is_owner = u.id == super_admin.id
                                m_role = "owner" if is_owner else ("admin" if role_norm in ("super_admin", "hr_manager") else "member")
                                session.add(ChatConversationMember(
                                    conversation_id=conv.id,
                                    user_id=u.id,
                                    role=m_role,
                                    joined_at=_now_utc(),
                                ))
                        # Add welcome message
                        session.add(ChatMessage(
                            conversation_id=conv.id,
                            sender_id=super_admin.id,
                            sender_name=super_admin.name,
                            sender_role=super_admin.role,
                            content=f"Welcome to #{conv.title}! {conv.description}",
                            message_type="system",
                            created_at=_now_utc(),
                        ))
                    else:
                        # Ensure all eligible users are members
                        existing_member_ids = set(session.scalars(
                            select(ChatConversationMember.user_id).where(
                                ChatConversationMember.conversation_id == existing.id
                            )
                        ).all())

                        for u in users:
                            if u.id not in existing_member_ids:
                                role_norm = _norm_role(u.role)
                                should_add = False
                                if ch.get("auto_join_all"):
                                    should_add = True
                                elif ch.get("auto_roles") and (u.role in ch["auto_roles"] or role_norm in ch["auto_roles"]):
                                    should_add = True
                                if should_add:
                                    session.add(ChatConversationMember(
                                        conversation_id=existing.id,
                                        user_id=u.id,
                                        role="member",
                                        joined_at=_now_utc(),
                                    ))

                session.commit()
        except Exception as exc:
            print(f"Warning: Default channel initialization notice: {exc}")

    # Run default channel sync once
    init_default_channels()

    # ─────────────────────────────────────────────────────────────────────────
    # REST API: Conversations
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/chat/conversations")
    @chat_auth_required
    def list_conversations():
        """Retrieve all conversations the current user is authorized to participate in."""
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            # Query conversations where user is a member, OR is_announcement=True for all active employees
            memberships = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).all()
            member_conv_ids = [m.conversation_id for m in memberships]
            membership_map = {m.conversation_id: m for m in memberships}

            # Also include company announcements if not already joined
            conv_query = select(ChatConversation).where(
                or_(
                    ChatConversation.id.in_(member_conv_ids) if member_conv_ids else False,
                    and_(ChatConversation.is_announcement.is_(True), ChatConversation.is_archived.is_(False)),
                )
            ).order_by(desc(ChatConversation.updated_at))

            conv_rows = session.scalars(conv_query).all()
            result = []

            for conv in conv_rows:
                # Latest message
                last_msg = session.scalars(
                    select(ChatMessage).where(
                        ChatMessage.conversation_id == conv.id
                    ).order_by(desc(ChatMessage.id)).limit(1)
                ).first()

                # Unread count
                mem = membership_map.get(conv.id)
                unread_count = 0
                if mem and mem.last_read_message_id:
                    unread_count = session.scalar(
                        select(func.count(ChatMessage.id)).where(
                            and_(
                                ChatMessage.conversation_id == conv.id,
                                ChatMessage.id > mem.last_read_message_id,
                                ChatMessage.sender_id != user_id,
                                ChatMessage.is_deleted.is_(False),
                            )
                        )
                    ) or 0
                elif mem and not mem.last_read_message_id:
                    unread_count = session.scalar(
                        select(func.count(ChatMessage.id)).where(
                            and_(
                                ChatMessage.conversation_id == conv.id,
                                ChatMessage.sender_id != user_id,
                                ChatMessage.is_deleted.is_(False),
                            )
                        )
                    ) or 0

                item = conv.to_dict()
                item["unreadCount"] = unread_count
                item["isMuted"] = mem.is_muted if mem else False
                item["myRole"] = mem.role if mem else ("viewer" if conv.is_announcement else "member")
                item["lastMessage"] = last_msg.to_dict() if last_msg else None

                # For direct conversations, calculate peer profile details & presence
                if conv.type == "direct":
                    peer_member = session.scalars(
                        select(ChatConversationMember).where(
                            and_(
                                ChatConversationMember.conversation_id == conv.id,
                                ChatConversationMember.user_id != user_id,
                            )
                        )
                    ).first()
                    if peer_member:
                        peer_user = session.get(User, peer_member.user_id)
                        if peer_user:
                            is_online = peer_user.id in _online_users and len(_online_users[peer_user.id]["sids"]) > 0
                            item["peer"] = {
                                "id": peer_user.id,
                                "name": peer_user.name,
                                "email": peer_user.email,
                                "role": peer_user.role,
                                "isOnline": is_online,
                                "status": _online_users.get(peer_user.id, {}).get("status", "offline" if not is_online else "online"),
                            }
                            # Override title with peer's name if not explicitly set
                            if not item["title"]:
                                item["title"] = peer_user.name
                result.append(item)

            return jsonify(result)

    @app.post("/api/chat/conversations")
    @chat_auth_required
    def create_conversation():
        """Create a direct (1:1) or group/project conversation."""
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        data = request.get_json(silent=True) or {}
        conv_type = data.get("type") or ("direct" if (data.get("is_direct") or data.get("isDirect")) else "group")
        target_user_id = data.get("targetUserId") or data.get("target_user_id")
        title = clean(data.get("title") or data.get("name") or "", 150)
        description = clean(data.get("description", ""), 300)
        member_ids = data.get("memberIds") or data.get("member_ids") or []

        with _get_session() as session:
            # Direct 1:1 conversation check
            if conv_type == "direct":
                if not target_user_id:
                    return error("targetUserId is required for direct messages.")
                target_user_id = int(target_user_id)
                if target_user_id == user_id:
                    return error("You cannot start a direct conversation with yourself.")

                target_user = session.get(User, target_user_id)
                if not target_user or target_user.status in {"suspended", "inactive", "terminated"}:
                    return error("User not found or unavailable.", 404)
                if _norm_role(target_user.role) in DISALLOWED_CHAT_ROLES:
                    return error("Cannot start conversation with viewers or general users.", 403)

                # Check if direct conversation already exists between these 2 users
                user_convs = session.scalars(
                    select(ChatConversationMember.conversation_id).where(
                        ChatConversationMember.user_id == user_id
                    )
                ).all()

                if user_convs:
                    existing_conv_id = session.scalar(
                        select(ChatConversationMember.conversation_id).where(
                            and_(
                                ChatConversationMember.conversation_id.in_(user_convs),
                                ChatConversationMember.user_id == target_user_id,
                            )
                        )
                    )
                    if existing_conv_id:
                        existing_conv = session.get(ChatConversation, existing_conv_id)
                        if existing_conv and existing_conv.type == "direct":
                            d = existing_conv.to_dict()
                            d["peer"] = {
                                "id": target_user.id,
                                "name": target_user.name,
                                "email": target_user.email,
                                "role": target_user.role,
                                "isOnline": target_user.id in _online_users and len(_online_users[target_user.id]["sids"]) > 0,
                            }
                            return jsonify(d), 200

                # Create new direct conversation
                conv = ChatConversation(
                    type="direct",
                    title=f"{user['name']} & {target_user.name}",
                    description=None,
                    created_by_id=user_id,
                    created_at=_now_utc(),
                    updated_at=_now_utc(),
                )
                session.add(conv)
                session.flush()

                session.add(ChatConversationMember(
                    conversation_id=conv.id,
                    user_id=user_id,
                    role="owner",
                    joined_at=_now_utc(),
                ))
                session.add(ChatConversationMember(
                    conversation_id=conv.id,
                    user_id=target_user_id,
                    role="member",
                    joined_at=_now_utc(),
                ))
                session.commit()

                res_dict = conv.to_dict()
                res_dict["peer"] = {
                    "id": target_user.id,
                    "name": target_user.name,
                    "email": target_user.email,
                    "role": target_user.role,
                    "isOnline": target_user.id in _online_users and len(_online_users[target_user.id]["sids"]) > 0,
                }
                return jsonify(res_dict), 201

            # Group / Project / Department Conversation
            else:
                if not title:
                    return error("Conversation title is required.")

                # Only Super Admin, Admin, HR, and Team Lead can create groups
                if norm_role not in {"super_admin", "admin", "hr_manager", "team_lead"}:
                    return error("You do not have permission to create company groups.", 403)

                conv = ChatConversation(
                    type=conv_type,
                    title=title,
                    description=description,
                    created_by_id=user_id,
                    department=data.get("department"),
                    project_name=data.get("projectName"),
                    is_announcement=bool(data.get("isAnnouncement", False)),
                    created_at=_now_utc(),
                    updated_at=_now_utc(),
                )
                session.add(conv)
                session.flush()

                # Add creator as owner
                session.add(ChatConversationMember(
                    conversation_id=conv.id,
                    user_id=user_id,
                    role="owner",
                    joined_at=_now_utc(),
                ))

                # Add initial members
                valid_members = set(member_ids)
                if valid_members:
                    existing_users = session.scalars(
                        select(User).where(and_(User.id.in_(valid_members), User.status == "active", ~User.role.in_(DISALLOWED_CHAT_ROLES)))
                    ).all()
                    for u in existing_users:
                        if u.id != user_id:
                            session.add(ChatConversationMember(
                                conversation_id=conv.id,
                                user_id=u.id,
                                role="member",
                                joined_at=_now_utc(),
                            ))

                # Initial system message
                session.add(ChatMessage(
                    conversation_id=conv.id,
                    sender_id=user_id,
                    sender_name=user["name"],
                    sender_role=user.get("role", "admin"),
                    content=f"Group '{title}' created by {user['name']}.",
                    message_type="system",
                    created_at=_now_utc(),
                ))

                session.commit()
                audit(user, "chat_group_created", f"Created group {title} (ID: {conv.id})")
                return jsonify(conv.to_dict()), 201

    @app.get("/api/chat/conversations/<int:conv_id>")
    @chat_auth_required
    def get_conversation_details(conv_id):
        user = request.admin
        user_id = int(user["id"])

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv or conv.is_archived:
                return error("Conversation not found.", 404)

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not member and not conv.is_announcement and _norm_role(user.get("role")) != "super_admin":
                return error("You are not a member of this conversation.", 403)

            # Members list
            members = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).all()

            member_list = []
            for m in members:
                u = session.get(User, m.user_id)
                if u:
                    is_online = u.id in _online_users and len(_online_users[u.id]["sids"]) > 0
                    member_list.append({
                        "id": u.id,
                        "name": u.name,
                        "email": u.email,
                        "role": u.role,
                        "groupRole": m.role,
                        "joinedAt": m.joined_at.isoformat() if m.joined_at else None,
                        "isOnline": is_online,
                    })

            # Pinned messages
            pinned = session.scalars(
                select(ChatMessage).where(
                    and_(
                        ChatMessage.conversation_id == conv_id,
                        ChatMessage.is_pinned.is_(True),
                        ChatMessage.is_deleted.is_(False),
                    )
                ).order_by(desc(ChatMessage.pinned_at))
            ).all()

            resp = conv.to_dict()
            resp["members"] = member_list
            resp["pinnedMessages"] = [p.to_dict() for p in pinned]
            resp["myRole"] = member.role if member else "member"
            return jsonify(resp)

    @app.put("/api/chat/conversations/<int:conv_id>")
    @chat_auth_required
    def update_conversation(conv_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return error("Conversation not found.", 404)

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            is_owner = member and member.role in ("owner", "admin")
            if not is_owner and norm_role != "super_admin":
                return error("Only group owners, admins or Super Admin can edit group info.", 403)

            data = request.get_json(silent=True) or {}
            if "title" in data:
                conv.title = clean(data["title"], 150)
            if "description" in data:
                conv.description = clean(data["description"], 300)
            if "avatarUrl" in data:
                conv.avatar_url = data["avatarUrl"]
            if "isArchived" in data:
                conv.is_archived = bool(data["isArchived"])

            conv.updated_at = _now_utc()
            session.commit()
            return jsonify(conv.to_dict())

    @app.delete("/api/chat/conversations/<int:conv_id>/leave")
    @chat_auth_required
    def leave_conversation(conv_id):
        user = request.admin
        user_id = int(user["id"])

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return error("Conversation not found.", 404)
            if conv.type == "direct":
                return error("You cannot leave a direct conversation.")

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not member:
                return error("You are not an active member of this group.", 400)

            member.left_at = _now_utc()
            session.add(ChatMessage(
                conversation_id=conv_id,
                sender_id=user_id,
                sender_name=user["name"],
                sender_role=user.get("role", "employee"),
                content=f"{user['name']} left the conversation.",
                message_type="system",
                created_at=_now_utc(),
            ))
            session.commit()
            return jsonify({"message": "Successfully left the conversation."})

    @app.post("/api/chat/conversations/<int:conv_id>/members")
    @chat_auth_required
    def add_conversation_member(conv_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return error("Conversation not found.", 404)
            if conv.type == "direct":
                return error("Cannot add members to a direct message.")

            req_member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not (req_member and req_member.role in ("owner", "admin")) and norm_role not in ("super_admin", "hr_manager"):
                return error("Only group owners, group admins or HR/Admin can add members.", 403)

            data = request.get_json(silent=True) or {}
            target_id = int(data.get("userId") or data.get("user_id") or (data.get("user_ids") and data.get("user_ids")[0]) or 0)
            new_role = data.get("role", "member")
            target_user = session.get(User, target_id)
            if not target_user:
                return error("User not found.", 404)
            if _norm_role(target_user.role) in DISALLOWED_CHAT_ROLES:
                return error("Cannot add viewers or general users to conversations.", 403)

            existing = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == target_id,
                    )
                )
            ).first()

            if existing:
                existing.left_at = None
                existing.role = new_role
            else:
                session.add(ChatConversationMember(
                    conversation_id=conv_id,
                    user_id=target_id,
                    role=new_role,
                    joined_at=_now_utc(),
                ))

            session.add(ChatMessage(
                conversation_id=conv_id,
                sender_id=user_id,
                sender_name=user["name"],
                sender_role=user.get("role", "employee"),
                content=f"{user['name']} added {target_user.name} to the group.",
                message_type="system",
                created_at=_now_utc(),
            ))
            session.commit()
            return jsonify({"message": f"{target_user.name} added to group.", "success": True, "ok": True})

    @app.delete("/api/chat/conversations/<int:conv_id>/members/<int:target_id>")
    @chat_auth_required
    def remove_conversation_member(conv_id, target_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return error("Conversation not found.", 404)

            req_member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not (req_member and req_member.role in ("owner", "admin")) and norm_role not in ("super_admin", "hr_manager"):
                return error("Only group owners, group admins or HR/Admin can remove members.", 403)

            target_member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == target_id,
                    )
                )
            ).first()

            if not target_member:
                return error("Target user is not a member of this conversation.", 404)

            target_user = session.get(User, target_id)
            target_name = target_user.name if target_user else f"User {target_id}"

            session.delete(target_member)
            session.add(ChatMessage(
                conversation_id=conv_id,
                sender_id=user_id,
                sender_name=user["name"],
                sender_role=user.get("role", "employee"),
                content=f"{user['name']} removed {target_name} from the group.",
                message_type="system",
                created_at=_now_utc(),
            ))
            session.commit()
            return jsonify({"message": f"{target_name} removed from group."})

    # ─────────────────────────────────────────────────────────────────────────
    # REST API: Messages & History
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/chat/conversations/<int:conv_id>/messages")
    @chat_auth_required
    def get_messages(conv_id):
        """Retrieve paginated message history."""
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return error("Conversation not found.", 404)

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not member and not conv.is_announcement and norm_role != "super_admin":
                return error("Access denied to conversation history.", 403)

            limit = min(int(request.args.get("limit", 50)), 100)
            before_id = request.args.get("before_id")

            query = select(ChatMessage).where(
                ChatMessage.conversation_id == conv_id
            )
            if before_id:
                query = query.where(ChatMessage.id < int(before_id))

            messages = session.scalars(
                query.order_by(desc(ChatMessage.id)).limit(limit)
            ).all()

            # Return in chronological order
            res = [m.to_dict() for m in reversed(messages)]
            return jsonify(res)

    @app.post("/api/chat/conversations/<int:conv_id>/messages")
    @chat_auth_required
    def post_message(conv_id):
        """Send a message to a conversation."""
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv or conv.is_archived:
                return error("Conversation is unavailable or archived.", 404)

            # Role-based restriction: Announcements channel is read-only for non-admins/non-HR
            if conv.is_announcement and norm_role not in ("super_admin", "admin", "hr_manager", "hr"):
                return error("Only Super Admin and HR can post announcements in this channel.", 403)

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if not member and not conv.is_announcement and norm_role != "super_admin":
                return error("You are not a member of this conversation.", 403)

            data = request.get_json(silent=True) or {}
            content = clean(data.get("content", ""), 5000)
            reply_to_id = data.get("replyToId")
            attachments = data.get("attachments") or []

            if not content and not attachments:
                return error("Message content or attachment is required.")

            msg = ChatMessage(
                conversation_id=conv_id,
                sender_id=user_id,
                sender_name=user["name"],
                sender_role=user.get("role", "employee"),
                content=content or "(Attachment)",
                message_type="file" if attachments and not content else "text",
                reply_to_id=int(reply_to_id) if reply_to_id else None,
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            session.add(msg)
            session.flush()

            # Attachments
            for att in attachments:
                session.add(ChatMessageAttachment(
                    message_id=msg.id,
                    filename=clean(att.get("filename", "file"), 200),
                    file_url=att.get("fileUrl", ""),
                    file_type=att.get("fileType", "application/octet-stream"),
                    file_size=int(att.get("fileSize", 0)),
                    created_at=_now_utc(),
                ))

            # Auto mark read for sender
            if member:
                member.last_read_message_id = msg.id
                member.last_read_at = _now_utc()

            conv.updated_at = _now_utc()
            session.commit()

            msg_dict = msg.to_dict()

            # Broadcast real-time event to conversation room
            socketio.emit("new_message", msg_dict, room=f"conv_{conv_id}")

            # Notify offline or outside members
            members = session.scalars(
                select(ChatConversationMember.user_id).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.left_at.is_(None),
                        ChatConversationMember.user_id != user_id,
                    )
                )
            ).all()
            for m_uid in members:
                socketio.emit("conversation_alert", {
                    "conversationId": conv_id,
                    "title": conv.title,
                    "senderName": user["name"],
                    "content": msg.content,
                    "messageId": msg.id,
                }, room=f"user_{m_uid}")

            return jsonify(msg_dict), 201

    @app.put("/api/chat/messages/<int:msg_id>")
    @chat_auth_required
    def edit_message(msg_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            msg = session.get(ChatMessage, msg_id)
            if not msg or msg.is_deleted:
                return error("Message not found or deleted.", 404)

            if msg.sender_id != user_id and norm_role != "super_admin":
                return error("You can only edit your own messages.", 403)

            data = request.get_json(silent=True) or {}
            new_content = clean(data.get("content", ""), 5000)
            if not new_content:
                return error("Message content cannot be empty.")

            msg.content = new_content
            msg.is_edited = True
            msg.edited_at = _now_utc()
            session.commit()

            res = msg.to_dict()
            socketio.emit("message_edited", res, room=f"conv_{msg.conversation_id}")
            return jsonify(res)

    @app.delete("/api/chat/messages/<int:msg_id>")
    @chat_auth_required
    def delete_message(msg_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            msg = session.get(ChatMessage, msg_id)
            if not msg:
                return error("Message not found.", 404)

            # Senders can delete their message; Super Admin / HR can delete for moderation
            if msg.sender_id != user_id and norm_role not in ("super_admin", "admin", "hr_manager"):
                return error("You don't have permission to delete this message.", 403)

            msg.is_deleted = True
            msg.deleted_at = _now_utc()
            session.commit()

            socketio.emit("message_deleted", {
                "id": msg.id,
                "conversationId": msg.conversation_id,
            }, room=f"conv_{msg.conversation_id}")
            res = msg.to_dict()
            res["message"] = "Message deleted successfully."
            return jsonify(res)

    @app.post("/api/chat/messages/<int:msg_id>/react")
    @app.post("/api/chat/messages/<int:msg_id>/reactions")
    @chat_auth_required
    def react_message(msg_id):
        user = request.admin
        user_id = int(user["id"])

        data = request.get_json(silent=True) or {}
        emoji = clean(data.get("emoji") or data.get("reaction") or "👍", 20)
        if not emoji:
            return error("Emoji is required.")

        with _get_session() as session:
            msg = session.get(ChatMessage, msg_id)
            if not msg or msg.is_deleted:
                return error("Message not found.", 404)

            existing = session.scalars(
                select(ChatMessageReaction).where(
                    and_(
                        ChatMessageReaction.message_id == msg_id,
                        ChatMessageReaction.user_id == user_id,
                        ChatMessageReaction.emoji == emoji,
                    )
                )
            ).first()

            if existing:
                session.delete(existing)
                session.commit()
                action = "removed"
            else:
                session.add(ChatMessageReaction(
                    message_id=msg_id,
                    user_id=user_id,
                    user_name=user["name"],
                    emoji=emoji,
                    created_at=_now_utc(),
                ))
                session.commit()
                action = "added"

            # Fetch fresh reactions list
            reactions = session.scalars(
                select(ChatMessageReaction).where(ChatMessageReaction.message_id == msg_id)
            ).all()

            reactions_data = [r.to_dict() for r in reactions]
            socketio.emit("message_reactions_updated", {
                "messageId": msg_id,
                "conversationId": msg.conversation_id,
                "reactions": reactions_data,
            }, room=f"conv_{msg.conversation_id}")

            return jsonify({"action": action, "reactions": reactions_data})

    @app.post("/api/chat/messages/<int:msg_id>/pin")
    @chat_auth_required
    def pin_message(msg_id):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            msg = session.get(ChatMessage, msg_id)
            if not msg or msg.is_deleted:
                return error("Message not found.", 404)

            # Check if user can pin
            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == msg.conversation_id,
                        ChatConversationMember.user_id == user_id,
                    )
                )
            ).first()

            can_pin = (member and member.role in ("owner", "admin")) or norm_role in ("super_admin", "admin", "hr_manager")
            if not can_pin:
                return error("You don't have permission to pin messages in this conversation.", 403)

            msg.is_pinned = not msg.is_pinned
            msg.pinned_by_id = user_id if msg.is_pinned else None
            msg.pinned_at = _now_utc() if msg.is_pinned else None
            session.commit()

            socketio.emit("message_pinned", {
                "messageId": msg.id,
                "conversationId": msg.conversation_id,
                "isPinned": msg.is_pinned,
            }, room=f"conv_{msg.conversation_id}")

            return jsonify({"isPinned": msg.is_pinned, "is_pinned": msg.is_pinned})

    @app.post("/api/chat/conversations/<int:conv_id>/read")
    @chat_auth_required
    def mark_conversation_read(conv_id):
        user = request.admin
        user_id = int(user["id"])

        data = request.get_json(silent=True) or {}
        last_msg_id = data.get("lastMessageId")

        with _get_session() as session:
            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                    )
                )
            ).first()

            if not member:
                return jsonify({"ok": True})

            if not last_msg_id:
                latest = session.scalars(
                    select(ChatMessage.id).where(
                        ChatMessage.conversation_id == conv_id
                    ).order_by(desc(ChatMessage.id)).limit(1)
                ).first()
                last_msg_id = latest or 0

            member.last_read_message_id = int(last_msg_id)
            member.last_read_at = _now_utc()
            session.commit()

            socketio.emit("read_receipt", {
                "conversationId": conv_id,
                "userId": user_id,
                "lastReadMessageId": int(last_msg_id),
            }, room=f"conv_{conv_id}")

            return jsonify({"ok": True, "lastReadMessageId": int(last_msg_id)})

    @app.get("/api/chat/search")
    @chat_auth_required
    def search_messages():
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        q = clean(request.args.get("q", ""), 100).strip()
        conv_id = request.args.get("conversationId")
        if not q:
            return jsonify([])

        with _get_session() as session:
            # Authorized conversation IDs
            if conv_id:
                conv = session.get(ChatConversation, int(conv_id))
                if not conv:
                    return error("Conversation not found.", 404)
                allowed_ids = [conv.id]
            else:
                user_conv_ids = session.scalars(
                    select(ChatConversationMember.conversation_id).where(
                        ChatConversationMember.user_id == user_id
                    )
                ).all()
                ann_conv_ids = session.scalars(
                    select(ChatConversation.id).where(ChatConversation.is_announcement.is_(True))
                ).all()
                allowed_ids = list(set(user_conv_ids + ann_conv_ids))

            if not allowed_ids:
                return jsonify([])

            results = session.scalars(
                select(ChatMessage).where(
                    and_(
                        ChatMessage.conversation_id.in_(allowed_ids),
                        ChatMessage.content.ilike(f"%{q}%"),
                        ChatMessage.is_deleted.is_(False),
                    )
                ).order_by(desc(ChatMessage.id)).limit(30)
            ).all()

            return jsonify([r.to_dict() for r in results])

    @app.get("/api/chat/directory")
    @chat_auth_required
    def get_chat_directory():
        """Retrieve eligible company contacts for starting individual conversations."""
        user = request.admin
        user_id = int(user["id"])
        user_role = user.get("role", "employee")
        if _norm_role(user_role) in DISALLOWED_CHAT_ROLES:
            return jsonify([])

        directory = []
        try:
            with _get_session() as session:
                # Clients can only message Super Admin, HR, or assigned managers
                if user_role == "client":
                    allowed_roles = {"super_admin", "admin", "hr_manager", "team_lead"}
                    users = session.scalars(
                        select(User).where(and_(User.role.in_(allowed_roles), User.status == "active")).order_by(User.name)
                    ).all()
                else:
                    # Internal staff: strictly exclude clients, viewers, and general users
                    disallowed = {"client", "viewer", "user"}
                    users = session.scalars(
                        select(User).where(and_(User.status == "active", ~User.role.in_(disallowed))).order_by(User.name)
                    ).all()

                for u in users:
                    if u.id == user_id or _norm_role(u.role) in DISALLOWED_CHAT_ROLES:
                        continue
                    is_online = u.id in _online_users and len(_online_users[u.id]["sids"]) > 0
                    directory.append({
                        "id": u.id,
                        "name": u.name,
                        "email": u.email,
                        "role": u.role,
                        "isOnline": is_online,
                        "status": _online_users.get(u.id, {}).get("status", "offline" if not is_online else "online"),
                    })
        except Exception:
            raw_users = db.read("admins") or []
            allowed = {"super_admin", "admin", "hr_manager", "team_lead"} if user_role == "client" else None
            for u in sorted(raw_users, key=lambda x: str(x.get("name", "")).lower()):
                if u.get("id") == user_id:
                    continue
                r = str(u.get("role", "employee")).lower().strip()
                st = u.get("status", "active")
                if st != "active":
                    continue
                if r in DISALLOWED_CHAT_ROLES or r in ("user", "viewer"):
                    continue
                if user_role == "client" and r not in allowed:
                    continue
                if user_role != "client" and (r == "client" or r in DISALLOWED_CHAT_ROLES):
                    continue
                uid = u.get("id")
                is_online = uid in _online_users and len(_online_users[uid]["sids"]) > 0
                directory.append({
                    "id": uid,
                    "name": u.get("name", "User"),
                    "email": u.get("email", ""),
                    "role": r,
                    "isOnline": is_online,
                    "status": _online_users.get(uid, {}).get("status", "offline" if not is_online else "online"),
                })

        return jsonify(directory)

    @app.post("/api/chat/upload")
    @chat_auth_required
    def upload_attachment():
        """Upload file attachment with safe extension and size enforcement."""
        if "file" not in request.files:
            return error("No file provided.")
        file = request.files["file"]
        if not file or not file.filename:
            return error("Empty filename.")

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_CHAT_EXT:
            return error(f"Unsupported file type '{ext}'. Allowed: images, docs, audio, archives.")

        # Check file length
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_CHAT_UPLOAD_BYTES:
            return error(f"File exceeds maximum allowed size of {MAX_CHAT_UPLOAD_BYTES // (1024*1024)} MB.")

        unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"
        dest_path = os.path.join(upload_chat_dir, unique_name)
        file.save(dest_path)

        file_url = f"/api/chat/attachments/{unique_name}"
        return jsonify({
            "filename": filename,
            "fileUrl": file_url,
            "fileType": file.content_type or "application/octet-stream",
            "fileSize": size,
        }), 201

    @app.get("/api/chat/attachments/<path:filename>")
    @chat_auth_required
    def serve_attachment(filename):
        """Serve uploaded chat attachments to authenticated users."""
        safe_name = os.path.basename(filename)
        return send_from_directory(upload_chat_dir, safe_name)

    # ─────────────────────────────────────────────────────────────────────────
    # REST API: Video & Audio Meetings
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/meetings")
    @chat_auth_required
    def list_meetings():
        """Retrieve upcoming, live, and past meetings for current user."""
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            # Participant in meeting OR host OR department wide
            part_meeting_ids = session.scalars(
                select(MeetingParticipant.meeting_id).where(MeetingParticipant.user_id == user_id)
            ).all()

            query = select(Meeting).where(
                or_(
                    Meeting.host_id == user_id,
                    Meeting.id.in_(part_meeting_ids) if part_meeting_ids else False,
                    and_(Meeting.target_department == "All", Meeting.status.in_(("scheduled", "live"))),
                )
            ).order_by(desc(Meeting.scheduled_start or Meeting.created_at)).limit(50)

            meetings = session.scalars(query).all()
            res = []
            for m in meetings:
                d = m.to_dict()
                d["isHost"] = m.host_id == user_id
                part = session.scalars(
                    select(MeetingParticipant).where(
                        and_(MeetingParticipant.meeting_id == m.id, MeetingParticipant.user_id == user_id)
                    )
                ).first()
                d["myRsvp"] = part.invitation_status if part else ("host" if d["isHost"] else "invited")
                res.append(d)

            return jsonify(res)

    @app.post("/api/meetings")
    @app.post("/api/meetings/schedule")
    @chat_auth_required
    def schedule_meeting():
        """Schedule a new audio/video meeting with invited employees."""
        user = request.admin
        user_id = int(user["id"])
        data = request.get_json(silent=True) or {}

        title = clean(data.get("title", ""), 180)
        description = clean(data.get("description", ""), 500)
        scheduled_start = data.get("scheduledStart") or data.get("scheduled_start")
        scheduled_end = data.get("scheduledEnd") or data.get("scheduled_end")
        target_department = data.get("targetDepartment") or data.get("target_department")
        invited_user_ids = data.get("invitedUserIds") or data.get("invited_user_ids") or []

        if not title:
            return error("Meeting title is required.")

        start_dt = None
        if scheduled_start:
            try:
                start_dt = datetime.fromisoformat(scheduled_start.replace("Z", "+00:00"))
            except Exception:
                start_dt = _now_utc() + timedelta(minutes=15)
        else:
            start_dt = _now_utc() + timedelta(minutes=15)

        end_dt = None
        if scheduled_end:
            try:
                end_dt = datetime.fromisoformat(scheduled_end.replace("Z", "+00:00"))
            except Exception:
                end_dt = start_dt + timedelta(minutes=45)
        else:
            end_dt = start_dt + timedelta(minutes=45)

        meeting_code = f"kyk-{uuid.uuid4().hex[:8]}"

        with _get_session() as session:
            meet = Meeting(
                meeting_code=meeting_code,
                title=title,
                description=description,
                host_id=user_id,
                host_name=user["name"],
                status="scheduled",
                meeting_type="scheduled",
                scheduled_start=start_dt,
                scheduled_end=end_dt,
                target_department=target_department,
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            session.add(meet)
            session.flush()

            # Host participant
            session.add(MeetingParticipant(
                meeting_id=meet.id,
                user_id=user_id,
                user_name=user["name"],
                user_email=user["email"],
                user_role=user.get("role", "host"),
                invitation_status="accepted",
                attendance_status="absent",
            ))

            # Invite other users
            invited_set = set(invited_user_ids)
            if invited_set:
                users = session.scalars(
                    select(User).where(and_(User.id.in_(invited_set), ~User.role.in_(DISALLOWED_CHAT_ROLES), User.status == "active"))
                ).all()
                for u in users:
                    if u.id != user_id and _norm_role(u.role) not in DISALLOWED_CHAT_ROLES:
                        session.add(MeetingParticipant(
                            meeting_id=meet.id,
                            user_id=u.id,
                            user_name=u.name,
                            user_email=u.email,
                            user_role=u.role,
                            invitation_status="invited",
                            attendance_status="absent",
                        ))
                        # Real-time alert
                        socketio.emit("meeting_scheduled_alert", {
                            "meetingCode": meet.meeting_code,
                            "title": meet.title,
                            "hostName": user["name"],
                            "scheduledStart": meet.scheduled_start.isoformat(),
                        }, room=f"user_{u.id}")

            session.commit()
            audit(user, "meeting_scheduled", f"Scheduled meeting '{title}' (Code: {meeting_code})")
            return jsonify(meet.to_dict()), 201

    @app.post("/api/meetings/instant")
    @chat_auth_required
    def create_instant_meeting():
        """Instantly launch a meeting room."""
        user = request.admin
        user_id = int(user["id"])
        data = request.get_json(silent=True) or {}
        title = clean(data.get("title", f"{user['name']}'s Instant Meeting"), 180)

        meeting_code = f"kyk-now-{uuid.uuid4().hex[:8]}"

        with _get_session() as session:
            meet = Meeting(
                meeting_code=meeting_code,
                title=title,
                host_id=user_id,
                host_name=user["name"],
                status="live",
                meeting_type="instant",
                actual_start=_now_utc(),
                scheduled_start=_now_utc(),
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            session.add(meet)
            session.flush()

            session.add(MeetingParticipant(
                meeting_id=meet.id,
                user_id=user_id,
                user_name=user["name"],
                user_email=user["email"],
                user_role=user.get("role", "host"),
                invitation_status="accepted",
                attendance_status="joined",
                joined_at=_now_utc(),
            ))
            session.commit()

            audit(user, "meeting_instant_started", f"Started instant meeting '{title}' ({meeting_code})")
            return jsonify(meet.to_dict()), 201

    @app.get("/api/meetings/<meeting_code>")
    @chat_auth_required
    def get_meeting(meeting_code):
        user = request.admin
        user_id = int(user["id"])

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet:
                return error("Meeting not found.", 404)

            participants = session.scalars(
                select(MeetingParticipant).where(MeetingParticipant.meeting_id == meet.id)
            ).all()

            d = meet.to_dict()
            d["isHost"] = meet.host_id == user_id
            d["participants"] = [p.to_dict() for p in participants]
            return jsonify(d)

    @app.post("/api/meetings/<meeting_code>/rsvp")
    @chat_auth_required
    def rsvp_meeting(meeting_code):
        user = request.admin
        user_id = int(user["id"])
        data = request.get_json(silent=True) or {}
        status = data.get("status", "accepted")  # accepted, declined

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet:
                return error("Meeting not found.", 404)

            part = session.scalars(
                select(MeetingParticipant).where(
                    and_(MeetingParticipant.meeting_id == meet.id, MeetingParticipant.user_id == user_id)
                )
            ).first()

            if not part:
                part = MeetingParticipant(
                    meeting_id=meet.id,
                    user_id=user_id,
                    user_name=user["name"],
                    user_email=user["email"],
                    user_role=user.get("role", "employee"),
                    invitation_status=status,
                    attendance_status="absent",
                )
                session.add(part)
            else:
                part.invitation_status = status

            session.commit()
            return jsonify({"ok": True, "success": True, "invitationStatus": status})

    @app.post("/api/meetings/<meeting_code>/end")
    @chat_auth_required
    def end_meeting(meeting_code):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet:
                return error("Meeting not found.", 404)

            if meet.host_id != user_id and norm_role != "super_admin":
                return error("Only the meeting host or Super Admin can terminate the meeting.", 403)

            meet.status = "completed"
            meet.actual_end = _now_utc()
            session.commit()

            socketio.emit("meeting_ended_by_host", {
                "meetingCode": meeting_code,
                "endedBy": user["name"],
            }, room=f"meeting_{meeting_code}")

            audit(user, "meeting_ended", f"Ended meeting {meeting_code}")
            return jsonify({"message": "Meeting completed successfully.", "status": "completed", "success": True, "ok": True})

    @app.get("/api/meetings/<meeting_code>/attendance")
    @chat_auth_required
    def get_meeting_attendance(meeting_code):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet:
                return error("Meeting not found.", 404)

            if meet.host_id != user_id and norm_role not in ("super_admin", "admin", "hr_manager"):
                return error("Only the host, HR, or Super Admin can view meeting attendance records.", 403)

            participants = session.scalars(
                select(MeetingParticipant).where(MeetingParticipant.meeting_id == meet.id)
            ).all()

            return jsonify([p.to_dict() for p in participants])

    @app.get("/api/meetings/<meeting_code>/chat")
    @chat_auth_required
    def get_meeting_chat(meeting_code):
        user = request.admin
        user_id = int(user["id"])
        norm_role = _norm_role(user.get("role"))

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet:
                return error("Meeting not found.", 404)

            # Check authorization to access meeting chat
            is_host = (meet.host_id == user_id)
            is_admin = (norm_role in ("super_admin", "admin", "hr_manager"))
            part = session.scalars(
                select(MeetingParticipant).where(
                    and_(MeetingParticipant.meeting_id == meet.id, MeetingParticipant.user_id == user_id)
                )
            ).first()
            is_invited = bool(part and part.invitation_status != "declined")
            dept = user.get("department")
            role = user.get("role")
            is_target = bool(
                (meet.target_department and dept and meet.target_department.lower() == dept.lower()) or
                (meet.target_role and role and meet.target_role.lower() == role.lower())
            )

            if not (is_host or is_admin or is_invited or is_target):
                return error("You are not authorized to view this meeting's chat messages.", 403)

            messages = session.scalars(
                select(MeetingChatMessage).where(
                    MeetingChatMessage.meeting_id == meet.id
                ).order_by(MeetingChatMessage.id)
            ).all()

            return jsonify([m.to_dict() for m in messages])

    # ─────────────────────────────────────────────────────────────────────────
    # Socket.IO Event Handlers
    # ─────────────────────────────────────────────────────────────────────────

    @socketio.on("connect")
    def handle_socket_connect(auth):
        """Authenticate socket connection using JWT token with session validation."""
        token = ""
        if isinstance(auth, dict):
            token = auth.get("token") or ""
        if not token:
            token = request.args.get("token", "")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        user = _user_from_token(token)
        if not user:
            return False  # Reject unauthenticated or revoked socket connection

        role_norm = _norm_role(user.get("role"))
        if role_norm in DISALLOWED_CHAT_ROLES:
            return False  # Viewers and general users cannot connect to real-time chat or meetings

        user_id = int(user["id"])
        sid = request.sid
        jti = user.get("_jti", "")

        _sid_to_user[sid] = user_id
        if jti:
            _sid_to_jti[sid] = jti

        is_staff = user.get("role") not in ("client", "viewer")
        if is_staff:
            join_room("staff_presence")

        if user_id not in _online_users:
            _online_users[user_id] = {
                "sids": set(),
                "user": {
                    "id": user_id,
                    "name": user["name"],
                    "email": user["email"],
                    "role": user.get("role", "employee"),
                },
                "status": "online",
                "last_seen": _now_utc().isoformat(),
            }
        _online_users[user_id]["sids"].add(sid)
        _online_users[user_id]["status"] = "online"

        join_room(f"user_{user_id}")

        # Broadcast online status only to authenticated staff members
        if is_staff:
            emit("user_presence_update", {
                "userId": user_id,
                "status": "online",
                "lastSeen": _now_utc().isoformat(),
            }, room="staff_presence")

        # Send initial self state & online users
        emit("connected_ready", {
            "userId": user_id,
            "onlineUserIds": [uid for uid, d in _online_users.items() if len(d["sids"]) > 0],
        })

    @socketio.on("disconnect")
    def handle_socket_disconnect():
        sid = request.sid
        _sid_to_jti.pop(sid, None)
        meeting_code = _sid_to_meeting.pop(sid, None)
        if meeting_code and meeting_code in _meeting_rooms:
            _meeting_rooms[meeting_code].discard(sid)
            if not _meeting_rooms[meeting_code]:
                _meeting_rooms.pop(meeting_code, None)

        user_id = _sid_to_user.pop(sid, None)
        if not user_id:
            return

        if user_id in _online_users:
            _online_users[user_id]["sids"].discard(sid)
            if not _online_users[user_id]["sids"]:
                now_str = _now_utc().isoformat()
                _online_users[user_id]["status"] = "offline"
                _online_users[user_id]["last_seen"] = now_str

                emit("user_presence_update", {
                    "userId": user_id,
                    "status": "offline",
                    "lastSeen": now_str,
                }, room="staff_presence")

    @socketio.on("join_conversation")
    def on_join_conversation(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id:
            return

        if not isinstance(data, dict):
            return

        conv_id = int(data.get("conversationId", 0))
        if not conv_id:
            return

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return

            member = session.scalars(
                select(ChatConversationMember).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.user_id == user_id,
                        ChatConversationMember.left_at.is_(None),
                    )
                )
            ).first()

            if member or conv.is_announcement:
                join_room(f"conv_{conv_id}")
                emit("joined_conversation_room", {"conversationId": conv_id})

    @socketio.on("leave_conversation")
    def on_leave_conversation(data):
        if not isinstance(data, dict):
            return
        conv_id = int(data.get("conversationId", 0))
        if conv_id:
            leave_room(f"conv_{conv_id}")

    @socketio.on("send_chat_message")
    def on_send_chat_message(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id or not isinstance(data, dict):
            return

        conv_id = int(data.get("conversationId", 0))
        content = clean(data.get("content", ""), 5000)
        reply_to_id = data.get("replyToId")
        attachments = data.get("attachments") or []

        if not conv_id or (not content and not attachments):
            return

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv or conv.is_archived:
                return

            user = session.get(User, user_id)
            if not user or user.status != "active":
                return

            # Check announcement write permissions
            if conv.is_announcement and _norm_role(user.role) not in ("super_admin", "admin", "hr_manager", "hr"):
                emit("error_notice", {"message": "Announcements channel is read-only for employees."})
                return

            # Verify conversation membership
            if not conv.is_announcement:
                is_member = session.scalars(
                    select(ChatConversationMember.id).where(
                        and_(
                            ChatConversationMember.conversation_id == conv_id,
                            ChatConversationMember.user_id == user_id,
                            ChatConversationMember.left_at.is_(None),
                        )
                    )
                ).first()
                if not is_member and _norm_role(user.role) not in ("super_admin", "admin"):
                    emit("error_notice", {"message": "You are not an authorized member of this conversation."})
                    return

            msg = ChatMessage(
                conversation_id=conv_id,
                sender_id=user.id,
                sender_name=user.name,
                sender_role=user.role,
                content=content or "(Attachment)",
                message_type="file" if attachments and not content else "text",
                reply_to_id=int(reply_to_id) if reply_to_id else None,
                created_at=_now_utc(),
                updated_at=_now_utc(),
            )
            session.add(msg)
            session.flush()

            for att in attachments:
                if isinstance(att, dict):
                    session.add(ChatMessageAttachment(
                        message_id=msg.id,
                        filename=clean(att.get("filename", "file"), 200),
                        file_url=clean(att.get("fileUrl", ""), 500),
                        file_type=clean(att.get("fileType", "application/octet-stream"), 100),
                        file_size=int(att.get("fileSize", 0)),
                        created_at=_now_utc(),
                    ))

            conv.updated_at = _now_utc()
            session.commit()

            msg_dict = msg.to_dict()
            emit("new_message", msg_dict, room=f"conv_{conv_id}")

            # Notify conversation members
            members = session.scalars(
                select(ChatConversationMember.user_id).where(
                    and_(
                        ChatConversationMember.conversation_id == conv_id,
                        ChatConversationMember.left_at.is_(None),
                        ChatConversationMember.user_id != user_id,
                    )
                )
            ).all()

            for m_uid in members:
                emit("conversation_alert", {
                    "conversationId": conv_id,
                    "title": conv.title,
                    "senderName": user.name,
                    "content": msg.content,
                    "messageId": msg.id,
                }, room=f"user_{m_uid}")

    @socketio.on("typing_start")
    def on_typing_start(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id or not isinstance(data, dict):
            return
        conv_id = int(data.get("conversationId", 0))
        if not conv_id:
            return

        with _get_session() as session:
            conv = session.get(ChatConversation, conv_id)
            if not conv:
                return
            if not conv.is_announcement:
                is_mem = session.scalars(
                    select(ChatConversationMember.id).where(
                        and_(
                            ChatConversationMember.conversation_id == conv_id,
                            ChatConversationMember.user_id == user_id,
                            ChatConversationMember.left_at.is_(None),
                        )
                    )
                ).first()
                if not is_mem:
                    return

        user_data = _online_users.get(user_id, {}).get("user", {})
        emit("user_typing", {
            "conversationId": conv_id,
            "userId": user_id,
            "userName": user_data.get("name", "Someone"),
        }, room=f"conv_{conv_id}", include_self=False)

    @socketio.on("typing_stop")
    def on_typing_stop(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id or not isinstance(data, dict):
            return
        conv_id = int(data.get("conversationId", 0))
        if not conv_id:
            return
        emit("user_stopped_typing", {
            "conversationId": conv_id,
            "userId": user_id,
        }, room=f"conv_{conv_id}", include_self=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Socket.IO: WebRTC Video / Audio Meeting Signaling
    # ─────────────────────────────────────────────────────────────────────────

    @socketio.on("join_meeting_room")
    def on_join_meeting_room(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id or not isinstance(data, dict):
            return

        meeting_code = clean(data.get("meetingCode", ""), 50)
        if not meeting_code:
            return

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet or meet.status in ("completed", "cancelled"):
                emit("meeting_error", {"message": "Meeting has ended or code is invalid."})
                return

            user = session.get(User, user_id)
            if not user or user.status != "active":
                emit("meeting_error", {"message": "Account is inactive or suspended."})
                return

            norm_role = _norm_role(user.role)
            if norm_role in DISALLOWED_CHAT_ROLES:
                emit("meeting_error", {"message": "Viewers and general users do not have permissions to join meetings."})
                return
            is_host = (meet.host_id == user_id)
            is_admin = (norm_role in ("super_admin", "admin", "hr_manager"))

            part = session.scalars(
                select(MeetingParticipant).where(
                    and_(MeetingParticipant.meeting_id == meet.id, MeetingParticipant.user_id == user_id)
                )
            ).first()
            is_invited = bool(part and part.invitation_status != "declined")
            dept = getattr(user, "department", None)
            is_target = bool(
                (meet.target_department and dept and meet.target_department.lower() == dept.lower()) or
                (meet.target_role and user.role and meet.target_role.lower() == user.role.lower())
            )

            # Enforce meeting authorization (SEC-02 / CHAT-02)
            if not (is_host or is_admin or is_invited or is_target):
                emit("meeting_error", {"message": "You are not authorized to join this meeting. An invitation or host approval is required."})
                return

            # Mark meeting live if scheduled
            if meet.status == "scheduled":
                meet.status = "live"
                meet.actual_start = _now_utc()

            if not part:
                part = MeetingParticipant(
                    meeting_id=meet.id,
                    user_id=user_id,
                    user_name=user.name,
                    user_email=user.email,
                    user_role=user.role,
                    invitation_status="accepted",
                    attendance_status="joined",
                    joined_at=_now_utc(),
                )
                session.add(part)
            else:
                part.attendance_status = "joined"
                if not part.joined_at:
                    part.joined_at = _now_utc()

            session.commit()

            # Room management & Socket binding (SEC-03)
            room_name = f"meeting_{meeting_code}"
            join_room(room_name)

            if meeting_code not in _meeting_rooms:
                _meeting_rooms[meeting_code] = set()
            _meeting_rooms[meeting_code].add(sid)
            _sid_to_meeting[sid] = meeting_code

            # Inform other meeting participants
            emit("peer_joined_meeting", {
                "sid": sid,
                "userId": user_id,
                "userName": user.name,
                "userRole": user.role,
                "isHost": meet.host_id == user_id,
            }, room=room_name, include_self=False)

            # Send list of existing active peers in room to newly joined user
            active_peers = []
            for peer_sid in _meeting_rooms[meeting_code]:
                if peer_sid != sid:
                    p_uid = _sid_to_user.get(peer_sid)
                    p_info = _online_users.get(p_uid, {}).get("user", {})
                    active_peers.append({
                        "sid": peer_sid,
                        "userId": p_uid,
                        "userName": p_info.get("name", "Participant"),
                        "userRole": p_info.get("role", "member"),
                    })

            emit("meeting_room_joined_success", {
                "meetingCode": meeting_code,
                "isHost": meet.host_id == user_id,
                "activePeers": active_peers,
            })

    @socketio.on("leave_meeting_room")
    def on_leave_meeting_room(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        meeting_code = clean(data.get("meetingCode", "") if isinstance(data, dict) else "", 50) or _sid_to_meeting.get(sid, "")
        if not meeting_code:
            return

        room_name = f"meeting_{meeting_code}"
        leave_room(room_name)

        if meeting_code in _meeting_rooms:
            _meeting_rooms[meeting_code].discard(sid)
            if not _meeting_rooms[meeting_code]:
                _meeting_rooms.pop(meeting_code, None)

        _sid_to_meeting.pop(sid, None)

        # Update attendance
        if user_id:
            try:
                with _get_session() as session:
                    meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
                    if meet:
                        part = session.scalars(
                            select(MeetingParticipant).where(
                                and_(MeetingParticipant.meeting_id == meet.id, MeetingParticipant.user_id == user_id)
                            )
                        ).first()
                        if part and part.joined_at:
                            part.attendance_status = "left"
                            part.left_at = _now_utc()
                            duration = int((part.left_at - part.joined_at).total_seconds())
                            part.duration_seconds = max(duration, 0)
                            session.commit()
            except Exception:
                pass

        emit("peer_left_meeting", {
            "sid": sid,
            "userId": user_id,
        }, room=room_name)

    @socketio.on("webrtc_signal")
    def on_webrtc_signal(data):
        """Route WebRTC signaling payload with strict meeting-room peer authorization (SEC-03)."""
        sender_sid = request.sid
        sender_uid = _sid_to_user.get(sender_sid)
        if not sender_uid or not isinstance(data, dict):
            return

        sender_meeting = _sid_to_meeting.get(sender_sid)
        if not sender_meeting:
            # Sender is not bound to any active authorized meeting room
            return

        target_sid = data.get("targetSid")
        payload = data.get("payload")
        if not target_sid or not payload:
            return

        # Target must be currently bound to the EXACT same meeting room
        target_meeting = _sid_to_meeting.get(target_sid)
        if target_meeting != sender_meeting:
            return
        if target_sid not in _meeting_rooms.get(sender_meeting, set()):
            return

        sender_info = _online_users.get(sender_uid, {}).get("user", {})
        emit("webrtc_signal_forward", {
            "senderSid": sender_sid,
            "senderUserId": sender_uid,
            "senderName": sender_info.get("name", "Peer"),
            "payload": payload,
        }, room=target_sid)

    @socketio.on("media_state_change")
    def on_media_state_change(data):
        sender_sid = request.sid
        if not isinstance(data, dict):
            return
        meeting_code = clean(data.get("meetingCode", ""), 50)
        # Verify sender is bound to this meeting (SEC-03 / CHAT-12)
        if not meeting_code or _sid_to_meeting.get(sender_sid) != meeting_code:
            return

        emit("peer_media_state", {
            "sid": sender_sid,
            "userId": _sid_to_user.get(sender_sid),
            "audioEnabled": bool(data.get("audioEnabled", True)),
            "videoEnabled": bool(data.get("videoEnabled", True)),
            "screenSharing": bool(data.get("screenSharing", False)),
        }, room=f"meeting_{meeting_code}", include_self=False)

    @socketio.on("send_meeting_chat")
    def on_send_meeting_chat(data):
        sid = request.sid
        user_id = _sid_to_user.get(sid)
        if not user_id or not isinstance(data, dict):
            return

        meeting_code = clean(data.get("meetingCode", ""), 50)
        content = clean(data.get("content", ""), 2000)
        if not meeting_code or not content:
            return

        # Verify sender is bound to this meeting room
        if _sid_to_meeting.get(sid) != meeting_code:
            return

        with _get_session() as session:
            meet = session.scalars(select(Meeting).where(Meeting.meeting_code == meeting_code)).first()
            if not meet or meet.status in ("completed", "cancelled"):
                return

            user = session.get(User, user_id)
            if not user or user.status != "active":
                return

            chat_msg = MeetingChatMessage(
                meeting_id=meet.id,
                sender_id=user.id,
                sender_name=user.name,
                sender_role=user.role,
                content=content,
                created_at=_now_utc(),
            )
            session.add(chat_msg)
            session.commit()

            msg_payload = chat_msg.to_dict()
            emit("new_meeting_chat", msg_payload, room=f"meeting_{meeting_code}")

    print("Real-time Enterprise Chat & Video Meeting routes registered.")
