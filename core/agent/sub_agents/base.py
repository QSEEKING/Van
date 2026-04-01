"""
子代理抽象基类
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from core.llm.base import BaseLLMProvider, Message, ToolDefinition


class SubAgentInput(BaseModel):
    """子代理输入"""
    task: str
    context: str = ""
    metadata: dict[str, Any] = {}


class SubAgentOutput(BaseModel):
    """子代理输出"""
    agent_type: str
    result: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = {}
    input_tokens: int = 0
    output_tokens: int = 0


class BaseSubAgent(ABC):
    """子代理抽象基类"""

    agent_type: str = ""
    description: str = ""

    def __init__(self, llm: BaseLLMProvider) -> None:
        self.llm = llm

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回该子代理的专用系统提示"""
        ...

    def get_tools(self) -> list[ToolDefinition]:
        """返回该子代理可用的工具列表（默认无工具）"""
        return []

    @abstractmethod
    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        """执行子代理任务"""
        ...

    async def _call_llm(
        self,
        messages: list[Message],
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """调用 LLM 并返回 (content, input_tokens, output_tokens)"""
        response = await self.llm.chat(
            messages=messages,
            system=self.get_system_prompt(),
            tools=self.get_tools() or None,
            max_tokens=max_tokens,
        )
        return response.content, response.usage.input_tokens, response.usage.output_tokens
