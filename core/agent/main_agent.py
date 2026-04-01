"""
Main Agent - 主代理引擎（ReAct 循环）
DEV-001 核心代理引擎
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import structlog

from core.llm.base import BaseLLMProvider, Message, ToolUseBlock
from tools.base import ExecutionContext, ToolRegistry, ToolResult

logger = structlog.get_logger(__name__)

# 主代理默认系统提示
MAIN_AGENT_SYSTEM_PROMPT = """You are CoPaw Code, an expert AI coding assistant similar to Claude Code.
You help developers with coding tasks through intelligent conversation and tool use.

## Your Capabilities
- Read, write, and edit files in the codebase
- Execute shell commands to build, test, and run code
- Search through code with grep and glob patterns
- Explore and understand complex codebases
- Plan and execute multi-step development tasks

## Working Principles
1. **Understand before acting**: Read relevant files before making changes
2. **Minimal footprint**: Only create/modify files necessary for the task
3. **Verify your work**: After making changes, verify they are correct
4. **Be transparent**: Explain what you're doing and why
5. **Ask when unclear**: If requirements are ambiguous, ask for clarification
6. **Security first**: Never execute potentially dangerous commands

## Tool Usage
- Use tools to gather information before responding
- Always read files before editing them
- Prefer targeted edits over full rewrites
- Use glob/grep to understand code structure

## Response Style
- Be concise and focused on the task
- Show code changes clearly
- Explain your reasoning for complex decisions
- Use markdown for code blocks and formatting

Remember: You are operating directly on the user's codebase. Be careful and precise."""


class AgentEvent:
    """代理执行事件（用于流式输出）"""

    def __init__(self, event_type: str, data: Any) -> None:
        self.event_type = event_type  # "text" | "tool_start" | "tool_end" | "done" | "error"
        self.data = data

    def __repr__(self) -> str:
        return f"AgentEvent(type={self.event_type!r}, data={str(self.data)[:80]!r})"


class MainAgent:
    """
    主代理 - CoPaw Code 的核心引擎
    实现 ReAct（Reasoning + Acting）循环：
      1. 接收用户消息
      2. LLM 推理 → 决定行动
      3. 执行工具调用
      4. 将结果返回 LLM 继续推理
      5. 循环直到 LLM 不再调用工具
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        tool_registry: ToolRegistry | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 20,
        working_dir: str = ".",
    ) -> None:
        self.llm = llm
        self.registry = tool_registry or ToolRegistry.get_instance()
        self.system_prompt = system_prompt or MAIN_AGENT_SYSTEM_PROMPT
        self.max_iterations = max_iterations
        self.working_dir = working_dir
        self._logger = logger.bind(agent="main")

    # ─── 单轮完整对话 ─────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[Message],
        session_id: str | None = None,
        extra_context: str | None = None,
    ) -> tuple[str, list[ToolResult]]:
        """
        执行完整 ReAct 循环，返回 (最终文本响应, 所有工具调用结果)
        """
        sid = session_id or str(uuid.uuid4())[:8]
        log = self._logger.bind(session_id=sid)

        # 构建系统提示（可追加额外上下文）
        system = self.system_prompt
        if extra_context:
            system = f"{system}\n\n## Additional Context\n{extra_context}"

        # 工具定义
        tool_defs = self.registry.get_definitions()

        # 工作副本（不修改原列表）
        working_messages = list(messages)
        all_tool_results: list[ToolResult] = []
        final_text = ""

        for iteration in range(self.max_iterations):
            log.debug("react_iteration", iteration=iteration)

            response = await self.llm.chat(
                messages=working_messages,
                tools=tool_defs if tool_defs else None,
                system=system,
                max_tokens=8192,
            )

            log.debug(
                "llm_response",
                finish_reason=response.finish_reason,
                tool_uses=len(response.tool_uses),
                tokens=response.usage.total_tokens,
            )

            # 追加 assistant 消息
            if response.content or response.tool_uses:
                assistant_content: list[dict[str, Any]] = []
                if response.content:
                    assistant_content.append({"type": "text", "text": response.content})
                for tu in response.tool_uses:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tu.id,
                        "name": tu.name,
                        "input": tu.input,
                    })
                working_messages.append(Message(
                    role="assistant",
                    content=assistant_content if len(assistant_content) > 1 else response.content,
                ))

            # 无工具调用 → 结束
            if not response.tool_uses or response.finish_reason == "end_turn":
                final_text = response.content
                break

            # 执行工具调用（并发）
            ctx = ExecutionContext(
                session_id=sid,
                working_dir=self.working_dir,
            )
            tool_results = await self._execute_tools_parallel(response.tool_uses, ctx)
            all_tool_results.extend(tool_results)

            # 将工具结果追加到消息
            for result in tool_results:
                # 找到对应的 tool_use id
                tu_id = next(
                    (tu.id for tu in response.tool_uses if tu.name == result.tool_name),
                    result.tool_name,
                )
                working_messages.append(Message(
                    role="tool",
                    content=result.to_llm_content(),
                    tool_call_id=tu_id,
                    name=result.tool_name,
                ))

        else:
            log.warning("max_iterations_reached", max=self.max_iterations)
            final_text = (
                f"[Warning: reached maximum {self.max_iterations} iterations]\n" + final_text
            )

        return final_text, all_tool_results

    # ─── 流式对话 ─────────────────────────────────────────────────────────────

    async def chat_stream(
        self,
        messages: list[Message],
        session_id: str | None = None,
        extra_context: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """
        流式执行 ReAct 循环，逐步 yield AgentEvent：
          - text 事件：LLM 生成的文本片段
          - tool_start 事件：开始调用工具
          - tool_end 事件：工具调用完成
          - done 事件：整个循环结束
        """
        sid = session_id or str(uuid.uuid4())[:8]
        system = self.system_prompt
        if extra_context:
            system = f"{system}\n\n## Additional Context\n{extra_context}"

        tool_defs = self.registry.get_definitions()
        working_messages = list(messages)

        for iteration in range(self.max_iterations):
            # 流式获取 LLM 响应
            text_buffer = ""
            tool_uses_buffer: dict[str, dict] = {}  # id -> {name, input_json}
            finish_reason = None

            async for chunk in self.llm.chat_stream(
                messages=working_messages,
                tools=tool_defs if tool_defs else None,
                system=system,
                max_tokens=8192,
            ):
                if chunk.content:
                    text_buffer += chunk.content
                    yield AgentEvent("text", chunk.content)
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason

            # 收集完成后的 tool_uses（非流式方式补充）
            if finish_reason == "tool_use":
                response = await self.llm.chat(
                    messages=working_messages,
                    tools=tool_defs if tool_defs else None,
                    system=system,
                    max_tokens=8192,
                )
                tool_uses = response.tool_uses
                if text_buffer == "" and response.content:
                    text_buffer = response.content
                    yield AgentEvent("text", response.content)
            else:
                tool_uses = []

            # 追加 assistant 消息
            working_messages.append(Message(role="assistant", content=text_buffer))

            if not tool_uses:
                break

            # 执行工具并流式报告
            ctx = ExecutionContext(session_id=sid, working_dir=self.working_dir)
            for tu in tool_uses:
                yield AgentEvent("tool_start", {"name": tu.name, "input": tu.input})

            results = await self._execute_tools_parallel(tool_uses, ctx)

            for result in results:
                yield AgentEvent("tool_end", {
                    "name": result.tool_name,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                    "result_preview": str(result.result or result.error or "")[:200],
                })
                tu_id = next(
                    (tu.id for tu in tool_uses if tu.name == result.tool_name),
                    result.tool_name,
                )
                working_messages.append(Message(
                    role="tool",
                    content=result.to_llm_content(),
                    tool_call_id=tu_id,
                    name=result.tool_name,
                ))
        else:
            yield AgentEvent("error", f"Max iterations ({self.max_iterations}) reached")

        yield AgentEvent("done", None)

    # ─── 工具执行（并发） ─────────────────────────────────────────────────────

    async def _execute_tools_parallel(
        self,
        tool_uses: list[ToolUseBlock],
        ctx: ExecutionContext,
    ) -> list[ToolResult]:
        """并发执行多个工具调用"""
        tasks = [
            self.registry.execute(tu.name, tu.input, ctx)
            for tu in tool_uses
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_results: list[ToolResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tool_results.append(ToolResult(
                    tool_name=tool_uses[i].name,
                    success=False,
                    error=str(result),
                ))
            else:
                tool_results.append(result)

        return tool_results
