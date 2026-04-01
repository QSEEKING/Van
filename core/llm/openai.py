"""
OpenAI LLM Provider 实现
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import openai as oai

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
    result = []
    for msg in messages:
        if msg.role == "tool":
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            })
        else:
            result.append({
                "role": msg.role,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            })
    return result


def _convert_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT Provider"""

    def __init__(self, api_key: str, model: str = "gpt-4o", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._client = oai.AsyncOpenAI(api_key=api_key)

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ChatResponse:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(_convert_messages(messages))

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": all_messages,
        }
        if tools:
            params["tools"] = _convert_tools(tools)
            params["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**params)
        choice = response.choices[0]
        msg = choice.message

        tool_uses: list[ToolUseBlock] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                import json
                tool_uses.append(ToolUseBlock(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                ))

        usage = Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return ChatResponse(
            content=msg.content or "",
            tool_uses=tool_uses,
            usage=usage,
            finish_reason=choice.finish_reason or "stop",
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
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(_convert_messages(messages))

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": all_messages,
            "stream": True,
        }
        if tools:
            params["tools"] = _convert_tools(tools)

        async for chunk in await self._client.chat.completions.create(**params):
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if delta.content:
                yield ChatChunk(content=delta.content)
            if choice.finish_reason:
                yield ChatChunk(finish_reason=choice.finish_reason)

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self.model)
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4
