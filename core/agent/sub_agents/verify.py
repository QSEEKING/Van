"""
Verify Agent - 代码验证和测试子代理
"""
from __future__ import annotations

from core.llm.base import Message, ToolDefinition
from tools.base import ToolRegistry

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class VerifyAgent(BaseSubAgent):
    """验证代理：代码验证、测试、质量检查"""

    agent_type = "verify"
    description = "验证代码实现的正确性，运行测试，进行代码质量评估"

    def __init__(self, llm, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self._registry = tool_registry or ToolRegistry.get_instance()

    def get_system_prompt(self) -> str:
        return """You are an expert code verification agent. Your job is to:
1. Review code changes for correctness and completeness
2. Identify potential bugs, edge cases, and logical errors
3. Check code against requirements and specifications
4. Suggest test cases to validate the implementation
5. Assess code quality: readability, maintainability, performance

Verification checklist:
- Does the code fulfill the stated requirements?
- Are error cases handled properly?
- Are there any potential security issues?
- Is the code well-documented?
- Are there any obvious performance issues?
- Does it follow the project's coding conventions?

Provide a structured verification report with:
- PASS/FAIL status for each criterion
- Specific issues found with line references
- Recommended fixes or improvements"""

    def get_tools(self) -> list[ToolDefinition]:
        return [
            t.to_definition()
            for t in self._registry.get_all()
            if t.name in ("read_file", "glob_search", "grep_search", "execute_shell_command")
        ]

    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        messages = [
            Message(
                role="user",
                content=(
                    f"Please verify the following:\n\n{input.task}\n\n"
                    f"Context:\n{input.context}" if input.context
                    else f"Please verify the following:\n\n{input.task}"
                ),
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
