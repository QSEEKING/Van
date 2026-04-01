"""
数据库模型 - 基于 SQLAlchemy ORM
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class SessionStatus(str, PyEnum):
    """会话状态枚举"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MemoryType(str, PyEnum):
    """记忆类型枚举"""
    FACT = "fact"
    PREFERENCE = "preference"
    CONTEXT = "context"
    TASK = "task"
    ERROR = "error"
    SUMMARY = "summary"


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class Session(Base):
    """会话表 - 存储会话信息"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())[:8],
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        Text,
        nullable=True,
        comment="JSON格式的元数据",
    )

    # 关系
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    memories: Mapped[list["Memory"]] = relationship(
        "Memory",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_sessions_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Message(Base):
    """消息表 - 存储对话消息"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
        index=True,
    )

    # 关系
    session: Mapped["Session"] = relationship("Session", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, session_id={self.session_id}, role={self.role})>"


class Memory(Base):
    """记忆表 - 存储长期记忆"""
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType),
        default=MemoryType.FACT,
        nullable=False,
        index=True,
    )
    importance: Mapped[int] = mapped_column(Integer, default=5)  # 1-10 重要程度
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # 关键词列表，逗号分隔
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 向量ID
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=True,
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # 关系
    session: Mapped["Session | None"] = relationship("Session", back_populates="memories")

    __table_args__ = (
        Index("idx_memories_user_type", "user_id", "memory_type"),
    )

    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, type={self.memory_type})>"


class ToolCall(Base):
    """工具调用表 - 记录工具调用日志"""
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    params: Mapped[str] = mapped_column(Text, nullable=False)  # JSON格式参数
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON格式结果
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
        index=True,
    )

    # 关系
    session: Mapped["Session"] = relationship("Session", back_populates="tool_calls")

    __table_args__ = (
        Index("idx_tool_calls_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ToolCall(id={self.id}, tool={self.tool_name}, success={self.success})>"


class UserConfig(Base):
    """用户配置表 - 存储用户偏好设置"""
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_user_configs_user_key", "user_id", "config_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserConfig(user_id={self.user_id}, key={self.config_key})>"
