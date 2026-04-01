"""
会话记忆 - 管理当前对话的短期记忆
DEV-004 记忆系统组件
"""
from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from typing import Any

import structlog
from pydantic import BaseModel, Field

from core.llm.base import Message

logger = structlog.get_logger(__name__)


class SessionMemory(BaseModel):
    """会话记忆数据结构"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    # 对话历史
    messages: list[Message] = Field(default_factory=list)

    # 工作目录
    working_dir: str = "."

    # 会话元数据
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Token 统计
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # 摘要（当历史过长时的压缩版本）
    summary: str | None = None
    summary_turn: int = 0  # 摘要涵盖的对话轮数

    @property
    def turn_count(self) -> int:
        """对话轮数"""
        return len([m for m in self.messages if m.role == "user"])

    @property
    def total_tokens(self) -> int:
        """总 token 数"""
        return self.total_input_tokens + self.total_output_tokens

    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self.messages.append(message)
        self.updated_at = time.time()

    def add_user_message(self, content: str) -> Message:
        """添加用户消息"""
        msg = Message(role="user", content=content)
        self.add_message(msg)
        return msg

    def add_assistant_message(
        self,
        content: str,
        tool_uses: list[dict] | None = None
    ) -> Message:
        """添加助手消息"""
        if tool_uses:
            # 将工具调用作为结构化内容
            content_blocks = [{"type": "text", "text": content}]
            for tu in tool_uses:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tu.get("id", str(uuid.uuid4())[:8]),
                    "name": tu["name"],
                    "input": tu.get("input", {})
                })
            msg = Message(role="assistant", content=content_blocks)
        else:
            msg = Message(role="assistant", content=content)
        self.add_message(msg)
        return msg

    def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: str,
        is_error: bool = False
    ) -> Message:
        """添加工具执行结果"""
        content = result if not is_error else f"[Error] {result}"
        msg = Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=tool_name
        )
        self.add_message(msg)
        return msg

    def get_recent_messages(self, n: int = 10) -> list[Message]:
        """获取最近 n 条消息"""
        return self.messages[-n:] if n > 0 else []

    def clear_messages(self) -> None:
        """清空消息历史"""
        self.messages.clear()
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "working_dir": self.working_dir,
            "metadata": self.metadata,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "summary": self.summary,
            "summary_turn": self.summary_turn,
            "message_count": len(self.messages),
            "turn_count": self.turn_count,
        }


class SessionManager:
    """
    会话管理器 - 管理多个会话的生命周期
    
    支持功能：
    - 创建/切换/关闭会话
    - 会话持久化
    - 会话历史浏览
    - LRU 缓存淘汰
    """

    def __init__(
        self,
        max_sessions: int = 100,
        session_max_tokens: int = 8000,
    ) -> None:
        self._sessions: OrderedDict[str, SessionMemory] = OrderedDict()
        self._max_sessions = max_sessions
        self._session_max_tokens = session_max_tokens
        self._current_session_id: str | None = None
        self._logger = logger.bind(component="SessionManager")

    def create_session(
        self,
        working_dir: str = ".",
        metadata: dict[str, Any] | None = None,
    ) -> SessionMemory:
        """创建新会话"""
        # 如果超过上限，淘汰最旧的会话
        if len(self._sessions) >= self._max_sessions:
            oldest_id = next(iter(self._sessions))
            self._sessions.pop(oldest_id)
            self._logger.info("evicted_session", session_id=oldest_id)

        session = SessionMemory(
            working_dir=working_dir,
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        self._current_session_id = session.session_id
        self._logger.info(
            "created_session",
            session_id=session.session_id,
            working_dir=working_dir
        )
        return session

    def get_session(self, session_id: str | None = None) -> SessionMemory | None:
        """获取会话"""
        sid = session_id or self._current_session_id
        if not sid:
            return None

        session = self._sessions.get(sid)
        if session:
            # 移到最后表示最近使用
            self._sessions.move_to_end(sid)
        return session

    def get_or_create_session(
        self,
        working_dir: str = "."
    ) -> SessionMemory:
        """获取当前会话，没有则创建"""
        session = self.get_session()
        if session:
            return session
        return self.create_session(working_dir)

    def switch_session(self, session_id: str) -> SessionMemory | None:
        """切换到指定会话"""
        session = self._sessions.get(session_id)
        if session:
            self._current_session_id = session_id
            self._sessions.move_to_end(session_id)
            self._logger.info("switched_session", session_id=session_id)
        return session

    def close_session(self, session_id: str | None = None) -> bool:
        """关闭会话"""
        sid = session_id or self._current_session_id
        if not sid:
            return False

        if sid in self._sessions:
            self._sessions.pop(sid)
            if self._current_session_id == sid:
                self._current_session_id = None
            self._logger.info("closed_session", session_id=sid)
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话摘要"""
        return [s.to_dict() for s in self._sessions.values()]

    @property
    def current_session(self) -> SessionMemory | None:
        """当前会话"""
        return self.get_session()

    @property
    def session_count(self) -> int:
        """会话数量"""
        return len(self._sessions)
