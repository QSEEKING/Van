"""
Anthropic (Claude) LLM Provider 实现
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import anthropic

from .base import (
    BaseLLMProvider,
    ChatChunk,
    ChatResponse,
    Message,
    ToolDefinition,
    ToolUseBlock,
    Usage,
)


def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """将内部 Message 模型转为 Anthropic API 格式"""
    result = []
    for msg in messages:
        if msg.role == "tool":
            # tool_result 格式
            result.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                }],
            })
        elif isinstance(msg.content, list):
            result.append({"role": msg.role, "content": msg.content})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _convert_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """将内部 ToolDefinition 转为 Anthropic API 格式"""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-5", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ChatResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": _convert_messages(messages),
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = _convert_tools(tools)

        response = await self._client.messages.create(**params)

        # 解析响应内容
        text_parts: list[str] = []
        tool_uses: list[ToolUseBlock] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(ToolUseBlock(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        )

        return ChatResponse(
            content="\n".join(text_parts),
            tool_uses=tool_uses,
            usage=usage,
            finish_reason=response.stop_reason or "end_turn",
            model=response.model,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": _convert_messages(messages),
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = _convert_tools(tools)

        async with self._client.messages.stream(**params) as stream:
            async for event in stream:
                if hasattr(event, "type"):
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield ChatChunk(content=delta.text)
                        elif hasattr(delta, "partial_json"):
                            yield ChatChunk(tool_use_delta={"partial_json": delta.partial_json})
                    elif event.type == "message_delta":
                        if hasattr(event, "usage"):
                            yield ChatChunk(
                                finish_reason=event.delta.stop_reason,
                                usage=Usage(
                                    output_tokens=event.usage.output_tokens,
                                ),
                            )

    def count_tokens(self, text: str) -> int:
        """使用 tiktoken 估算 Claude token 数（近似值）"""
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # 降级：粗略估算（1 token ≈ 4 chars）
            return len(text) // 4
