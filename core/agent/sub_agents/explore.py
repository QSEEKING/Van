"""
Explore Agent - 代码探索和理解子代理
"""
from __future__ import annotations

from core.llm.base import Message, ToolDefinition
from tools.base import ToolRegistry

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class ExploreAgent(BaseSubAgent):
    """探索代理：代码探索、依赖分析、结构理解"""

    agent_type = "explore"
    description = "探索和理解代码库结构、依赖关系和实现逻辑"

    def __init__(self, llm, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self._registry = tool_registry or ToolRegistry.get_instance()

    def get_system_prompt(self) -> str:
        return """You are an expert code exploration agent. Your job is to:
1. Analyze and understand code repository structure
2. Identify key files, modules, and their relationships
3. Trace code execution paths and data flows
4. Identify dependencies and external integrations
5. Summarize findings clearly and concisely

When exploring code:
- Start with high-level structure (directory listing, README)
- Drill into key files relevant to the task
- Note important patterns, conventions, and architecture decisions
- Highlight potential issues or areas of interest

Be thorough but focused. Return structured findings."""

    def get_tools(self) -> list[ToolDefinition]:
        return [
            t.to_definition()
            for t in self._registry.get_all()
            if t.name in ("read_file", "glob_search", "grep_search")
        ]

    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        messages = [
            Message(
                role="user",
                content=f"Task: {input.task}\n\nContext:\n{input.context}" if input.context
                        else f"Task: {input.task}",
            )
        ]

        try:
            content, in_tok, out_tok = await self._call_llm(messages, max_tokens=4096)
            return SubAgentOutput(
                agent_type=self.agent_type,
                result=content,
                success=True,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
        except Exception as e:
            return SubAgentOutput(
                agent_type=self.agent_type,
                result="",
                success=False,
                error=str(e),
            )
