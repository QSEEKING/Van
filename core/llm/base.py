"""
LLM 抽象基类 - 统一不同 Provider 的接口
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

# ─── 数据模型 ────────────────────────────────────────────────────────────────

class Message(BaseModel):
    """对话消息"""
    role: str          # "system" | "user" | "assistant" | "tool"
    content: str | list[dict[str, Any]]
    tool_call_id: str | None = None   # tool result 时使用
    name: str | None = None


class ToolDefinition(BaseModel):
    """工具定义（传给 LLM 的 schema）"""
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolUseBlock(BaseModel):
    """LLM 返回的工具调用"""
    id: str
    name: str
    input: dict[str, Any]


class Usage(BaseModel):
    """Token 用量统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ChatResponse(BaseModel):
    """完整聊天响应"""
    content: str
    tool_uses: list[ToolUseBlock] = []
    usage: Usage = Usage()
    finish_reason: str = "end_turn"   # "end_turn" | "tool_use" | "max_tokens"
    model: str = ""
    stop_sequence: str | None = None


class ChatChunk(BaseModel):
    """流式输出块"""
    content: str = ""
    tool_use_delta: dict[str, Any] | None = None
    finish_reason: str | None = None
    usage: Usage | None = None


# ─── 抽象基类 ────────────────────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """LLM 提供者抽象基类"""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self._extra = kwargs

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ChatResponse:
        """发送非流式聊天请求"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        """发送流式聊天请求"""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算文本 token 数"""
        ...
