"""
长期记忆 - 持久化存储用户偏好、项目知识和重要对话
DEV-004 记忆系统组件
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class MemoryType(str, Enum):
    """记忆类型"""
    CONVERSATION = "conversation"   # 对话摘要
    PREFERENCE = "preference"       # 用户偏好
    PROJECT = "project"             # 项目知识
    ERROR_FIX = "error_fix"        # 错误修复记录
    DECISION = "decision"          # 重要决策
    CODEBASE = "codebase"          # 代码库结构


class MemoryEntry(BaseModel):
    """记忆条目"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    memory_type: MemoryType = MemoryType.CONVERSATION
    content: str                    # 记忆内容
    embedding: list[float] | None = None  # 向量嵌入（可选）

    # 元数据
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    expires_at: float | None = None  # 过期时间（可选）

    # 关联信息
    project_path: str | None = None  # 关联项目路径
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 重要性评分 (0-1)
    importance: float = 0.5

    # 访问统计
    access_count: int = 0
    last_accessed: float = Field(default_factory=time.time)

    def access(self) -> None:
        """记录访问"""
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """序列化"""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "project_path": self.project_path,
            "tags": self.tags,
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }


class MemoryBackend(ABC):
    """记忆存储后端抽象"""

    @abstractmethod
    async def save(self, entry: MemoryEntry) -> str:
        """保存记忆，返回 ID"""
        ...

    @abstractmethod
    async def get(self, entry_id: str) -> MemoryEntry | None:
        """获取记忆"""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        project_path: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """搜索记忆"""
        ...

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """删除记忆"""
        ...

    @abstractmethod
    async def list_all(
        self,
        memory_type: MemoryType | None = None,
        project_path: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """列出所有记忆"""
        ...


class InMemoryBackend(MemoryBackend):
    """内存存储后端（用于测试/开发）"""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._logger = logger.bind(backend="memory")

    async def save(self, entry: MemoryEntry) -> str:
        self._entries[entry.id] = entry
        self._logger.debug("saved_entry", entry_id=entry.id)
        return entry.id

    async def get(self, entry_id: str) -> MemoryEntry | None:
        entry = self._entries.get(entry_id)
        if entry:
            entry.access()
        return entry

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        project_path: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        results = []
        query_lower = query.lower()

        for entry in self._entries.values():
            # 过滤过期记忆
            if entry.is_expired():
                continue

            # 类型过滤
            if memory_type and entry.memory_type != memory_type:
                continue

            # 项目过滤
            if project_path and entry.project_path != project_path:
                continue

            # 标签过滤
            if tags and not all(t in entry.tags for t in tags):
                continue

            # 内容匹配
            if query_lower in entry.content.lower():
                entry.access()
                results.append(entry)

        # 按重要性和访问时间排序
        results.sort(key=lambda e: (e.importance, e.last_accessed), reverse=True)
        return results[:limit]

    async def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    async def list_all(
        self,
        memory_type: MemoryType | None = None,
        project_path: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        results = []
        for entry in self._entries.values():
            if entry.is_expired():
                continue
            if memory_type and entry.memory_type != memory_type:
                continue
            if project_path and entry.project_path != project_path:
                continue
            results.append(entry)

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]


class LongTermMemory:
    """
    长期记忆管理器
    
    支持功能：
    - 持久化存储记忆
    - 按类型/项目/标签搜索
    - 记忆重要性评分
    - 自动过期清理
    """

    def __init__(self, backend: MemoryBackend | None = None) -> None:
        self._backend = backend or InMemoryBackend()
        self._logger = logger.bind(component="LongTermMemory")

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        project_path: str | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        expires_in: float | None = None,  # 秒
    ) -> MemoryEntry:
        """创建并存储记忆"""
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in

        entry = MemoryEntry(
            memory_type=memory_type,
            content=content,
            project_path=project_path,
            tags=tags or [],
            importance=importance,
            metadata=metadata or {},
            expires_at=expires_at,
        )

        await self._backend.save(entry)
        self._logger.info(
            "created_memory",
            entry_id=entry.id,
            memory_type=memory_type.value,
            importance=importance,
        )
        return entry

    async def recall(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        project_path: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """搜索记忆"""
        return await self._backend.search(
            query=query,
            memory_type=memory_type,
            project_path=project_path,
            tags=tags,
            limit=limit,
        )

    async def get(self, entry_id: str) -> MemoryEntry | None:
        """获取特定记忆"""
        return await self._backend.get(entry_id)

    async def forget(self, entry_id: str) -> bool:
        """删除记忆"""
        result = await self._backend.delete(entry_id)
        if result:
            self._logger.info("forgot_memory", entry_id=entry_id)
        return result

    async def get_project_knowledge(self, project_path: str) -> list[MemoryEntry]:
        """获取项目相关所有知识"""
        return await self._backend.list_all(
            memory_type=MemoryType.PROJECT,
            project_path=project_path,
            limit=50,
        )

    async def get_user_preferences(self) -> list[MemoryEntry]:
        """获取用户偏好"""
        return await self._backend.list_all(
            memory_type=MemoryType.PREFERENCE,
            limit=20,
        )

    async def save_conversation_summary(
        self,
        summary: str,
        project_path: str | None = None,
        important: bool = False,
    ) -> MemoryEntry:
        """保存对话摘要"""
        return await self.remember(
            content=summary,
            memory_type=MemoryType.CONVERSATION,
            project_path=project_path,
            importance=0.8 if important else 0.5,
        )

    async def save_preference(
        self,
        key: str,
        value: Any,
        description: str = "",
    ) -> MemoryEntry:
        """保存用户偏好"""
        content = f"{key}: {value}"
        if description:
            content += f"\n{description}"

        return await self.remember(
            content=content,
            memory_type=MemoryType.PREFERENCE,
            tags=["preference", key],
            importance=0.9,  # 偏好通常很重要
        )

    async def save_error_fix(
        self,
        error: str,
        fix: str,
        project_path: str | None = None,
    ) -> MemoryEntry:
        """保存错误修复记录"""
        content = f"Error: {error}\nFix: {fix}"
        return await self.remember(
            content=content,
            memory_type=MemoryType.ERROR_FIX,
            project_path=project_path,
            tags=["error", "fix"],
            importance=0.7,
        )
