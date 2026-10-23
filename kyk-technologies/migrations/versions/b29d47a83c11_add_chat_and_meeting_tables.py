"""add chat and meeting tables

Revision ID: b29d47a83c11
Revises: efcbb17ae78b
Create Date: 2026-10-17 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b29d47a83c11'
down_revision: Union[str, Sequence[str], None] = 'efcbb17ae78b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Explicit Alembic DDL for Enterprise Real-Time Chat & Video Meeting Tables (DB-04)
    from sqlalchemy.engine.reflection import Inspector
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    existing_tables = set(insp.get_table_names())

    if "chat_conversations" not in existing_tables:
        op.create_table(
            "chat_conversations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("type", sa.String(50), nullable=False, server_default="direct"),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(255), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("department", sa.String(100), nullable=True),
            sa.Column("project_name", sa.String(100), nullable=True),
            sa.Column("is_announcement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "chat_conversation_members" not in existing_tables:
        op.create_table(
            "chat_conversation_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(50), nullable=False, server_default="member"),
            sa.Column("is_muted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_read_message_id", sa.Integer(), nullable=True),
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("conversation_id", "user_id", name="uq_conv_user"),
        )

    if "chat_messages" not in existing_tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_name", sa.String(150), nullable=False),
            sa.Column("sender_role", sa.String(50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("message_type", sa.String(50), nullable=False, server_default="text"),
            sa.Column("reply_to_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("pinned_by_id", sa.Integer(), nullable=True),
            sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "chat_message_attachments" not in existing_tables:
        op.create_table(
            "chat_message_attachments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("file_url", sa.String(255), nullable=False),
            sa.Column("file_type", sa.String(100), server_default="application/octet-stream"),
            sa.Column("file_size", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "chat_message_reactions" not in existing_tables:
        op.create_table(
            "chat_message_reactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_name", sa.String(150), nullable=False),
            sa.Column("emoji", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_msg_user_emoji"),
        )

    if "chat_message_read_receipts" not in existing_tables:
        op.create_table(
            "chat_message_read_receipts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("message_id", "user_id", name="uq_msg_user_read"),
        )

    if "meetings" not in existing_tables:
        op.create_table(
            "meetings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("meeting_code", sa.String(50), unique=True, nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("host_name", sa.String(150), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="scheduled"),
            sa.Column("meeting_type", sa.String(50), nullable=False, server_default="scheduled"),
            sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("target_department", sa.String(100), nullable=True),
            sa.Column("target_role", sa.String(50), nullable=True),
            sa.Column("is_recorded", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("recording_url", sa.String(255), nullable=True),
            sa.Column("recording_status", sa.String(50), server_default="none"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "meeting_participants" not in existing_tables:
        op.create_table(
            "meeting_participants",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_name", sa.String(150), nullable=False),
            sa.Column("user_email", sa.String(255), nullable=False),
            sa.Column("user_role", sa.String(50), nullable=False),
            sa.Column("invitation_status", sa.String(50), nullable=False, server_default="invited"),
            sa.Column("attendance_status", sa.String(50), nullable=False, server_default="absent"),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), server_default="0"),
        )

    if "meeting_chat_messages" not in existing_tables:
        op.create_table(
            "meeting_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_name", sa.String(150), nullable=False),
            sa.Column("sender_role", sa.String(50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for tbl in [
        "meeting_chat_messages",
        "meeting_participants",
        "meetings",
        "chat_message_read_receipts",
        "chat_message_reactions",
        "chat_message_attachments",
        "chat_messages",
        "chat_conversation_members",
        "chat_conversations",
    ]:
        try:
            op.drop_table(tbl)
        except Exception:
            pass
