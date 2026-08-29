"""
NEXUS Database Models.

SQLAlchemy ORM models for all persistent data: conversations, messages,
tool calls, devices, memory, audit logs, and user preferences.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Base class for all NEXUS ORM models."""

    pass


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_profile_path: Mapped[str | None] = mapped_column(String(500))
    pin_hash: Mapped[str | None] = mapped_column(String(256))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    devices: Mapped[list[Device]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memory_entries: Mapped[list[MemoryEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list[Preference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    permission_rules: Mapped[list[PermissionRule]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, name={self.name!r})>"


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    auth_method: Mapped[str] = mapped_column(String(50), default="none")

    # Relationships
    user: Mapped[User] = relationship(back_populates="sessions")
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id!r}, user={self.user_id!r})>"


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    session: Mapped[Session] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id!r})>"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    tool_calls: Mapped[list[ToolCall]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id!r}, role={self.role!r})>"


# ---------------------------------------------------------------------------
# Tool Call
# ---------------------------------------------------------------------------


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, success, error
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    user_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    message: Mapped[Message] = relationship(back_populates="tool_calls")
    results: Mapped[list[ToolResult]] = relationship(
        back_populates="tool_call", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ToolCall(id={self.id!r}, tool={self.tool_name!r}, status={self.status!r})>"


# ---------------------------------------------------------------------------
# Tool Result
# ---------------------------------------------------------------------------


class ToolResult(Base):
    __tablename__ = "tool_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    tool_call_id: Mapped[str] = mapped_column(ForeignKey("tool_calls.id"), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result_data: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Relationships
    tool_call: Mapped[ToolCall] = relationship(back_populates="results")

    def __repr__(self) -> str:
        return f"<ToolResult(id={self.id!r}, success={self.success!r})>"


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # laptop, android
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    connection_info: Mapped[dict | None] = mapped_column(JSON)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="devices")
    states: Mapped[list[DeviceState]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id!r}, name={self.device_name!r}, type={self.device_type!r})>"


# ---------------------------------------------------------------------------
# Device State
# ---------------------------------------------------------------------------


class DeviceState(Base):
    __tablename__ = "device_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    device: Mapped[Device] = relationship(back_populates="states")

    def __repr__(self) -> str:
        return f"<DeviceState(id={self.id!r}, device={self.device_id!r})>"


# ---------------------------------------------------------------------------
# Memory Entry
# ---------------------------------------------------------------------------


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    memory_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # episodic, semantic, procedural
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict | None] = mapped_column("metadata", JSON)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped[User] = relationship(back_populates="memory_entries")

    def __repr__(self) -> str:
        return f"<MemoryEntry(id={self.id!r}, type={self.memory_type!r})>"


# ---------------------------------------------------------------------------
# Preference
# ---------------------------------------------------------------------------


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<Preference(key={self.key!r}, value={self.value!r})>"


# ---------------------------------------------------------------------------
# Permission Rule
# ---------------------------------------------------------------------------


class PermissionRule(Base):
    __tablename__ = "permission_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    tool_pattern: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # glob pattern, e.g. "file.*"
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # auto, confirm, deny
    risk_override: Mapped[str | None] = mapped_column(String(20))

    # Relationships
    user: Mapped[User] = relationship(back_populates="permission_rules")

    def __repr__(self) -> str:
        return f"<PermissionRule(pattern={self.tool_pattern!r}, action={self.action!r})>"


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"))
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    parameters: Mapped[dict | None] = mapped_column(JSON)
    result_status: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Relationships
    session: Mapped[Session | None] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action_type!r}, tool={self.tool_name!r})>"
