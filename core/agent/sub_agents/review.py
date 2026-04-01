"""
Review Agent - 代码审查子代理
"""
from __future__ import annotations

from core.llm.base import Message, ToolDefinition
from tools.base import ToolRegistry

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class ReviewAgent(BaseSubAgent):
    """审查代理：代码审查、质量检查、最佳实践验证"""

    agent_type = "review"
    description = "审查代码质量、发现潜在问题、验证最佳实践和代码规范"

    def __init__(self, llm, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self._registry = tool_registry or ToolRegistry.get_instance()

    def get_system_prompt(self) -> str:
        return """You are an expert code review agent. Your responsibilities include:

1. Code Quality Review
   - Check for code smells and anti-patterns
   - Identify potential bugs and edge cases
   - Review error handling and exception management
   - Assess code complexity and maintainability

2. Best Practices Validation
   - Verify adherence to coding standards (PEP8, etc.)
   - Check for proper documentation and comments
   - Review naming conventions
   - Assess code organization and structure

3. Security Review
   - Identify potential security vulnerabilities
   - Check for proper input validation
   - Review authentication and authorization patterns
   - Detect potential injection risks

4. Performance Review
   - Identify performance bottlenecks
   - Check for inefficient algorithms
   - Review resource usage patterns
   - Assess scalability concerns

Output your findings in a structured format:
- Summary: Overall assessment
- Critical Issues: Must-fix problems
- Warnings: Important but not critical
- Suggestions: Recommended improvements
- Best Practices: Positive aspects observed

Be thorough, constructive, and provide specific, actionable feedback."""

    def get_tools(self) -> list[ToolDefinition]:
        return [
            t.to_definition()
            for t in self._registry.get_all()
            if t.name in ("read_file", "grep_search", "glob_search")
        ]

    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        messages = [
            Message(
                role="user",
                content=f"Review Task: {input.task}\n\nContext:\n{input.context}"
                if input.context
                else f"Review Task: {input.task}",
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
                metadata={"review_type": input.metadata.get("review_type", "general")},
            )
        except Exception as e:
            return SubAgentOutput(
                agent_type=self.agent_type,
                result="",
                success=False,
                error=str(e),
            )
