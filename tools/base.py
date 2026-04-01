"""
工具基类 & 注册表 - DEV-003 工具系统核心
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from core.llm.base import ToolDefinition

# ─── 工具执行上下文 ───────────────────────────────────────────────────────────

class ExecutionContext(BaseModel):
    """工具执行上下文"""
    session_id: str = ""
    working_dir: str = "."
    timeout: int = 30
    sandbox_level: int = 1
    permissions: dict[str, bool] = {}
    metadata: dict[str, Any] = {}

    model_config = {"arbitrary_types_allowed": True}


# ─── 工具调用结果 ─────────────────────────────────────────────────────────────

class ToolResult(BaseModel):
    """工具执行结果"""
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: int = 0

    def to_llm_content(self) -> str:
        """转换为发送给 LLM 的内容字符串"""
        if self.success:
            if isinstance(self.result, str):
                return self.result
            import json
            return json.dumps(self.result, ensure_ascii=False, indent=2)
        else:
            return f"[Error] {self.error}"


# ─── 工具基类 ─────────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """所有工具的抽象基类"""

    name: str = ""
    description: str = ""
    requires_sandbox: bool = False
    timeout: int = 30

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """返回工具参数的 JSON Schema"""
        ...

    def to_definition(self) -> ToolDefinition:
        """转换为 LLM ToolDefinition"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.get_schema(),
        )

    @abstractmethod
    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> Any:
        """执行工具（子类实现具体逻辑）"""
        ...

    async def run(self, ctx: ExecutionContext, arguments: dict[str, Any]) -> ToolResult:
        """带计时、错误捕获的统一执行入口"""
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self.execute(ctx, **arguments),
                timeout=ctx.timeout or self.timeout,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                tool_name=self.name,
                success=True,
                result=result,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Tool execution timed out after {ctx.timeout or self.timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ─── 工具注册表 ───────────────────────────────────────────────────────────────

class ToolRegistry:
    """全局工具注册表（单例）"""

    _instance: ToolRegistry | None = None

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """注销工具"""
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_definitions(self) -> list[ToolDefinition]:
        """返回所有工具的 LLM 定义列表"""
        return [t.to_definition() for t in self._tools.values()]

    def get_names(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: ExecutionContext | None = None,
    ) -> ToolResult:
        """执行指定工具"""
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: '{tool_name}'",
            )
        if ctx is None:
            ctx = ExecutionContext()
        return await tool.run(ctx, arguments)
