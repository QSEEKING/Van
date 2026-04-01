"""
Security Review Agent - 安全审查子代理
"""
from __future__ import annotations

from core.llm.base import Message, ToolDefinition
from tools.base import ToolRegistry

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class SecurityAgent(BaseSubAgent):
    """安全审查代理：漏洞检测、安全建议、权限检查"""

    agent_type = "security"
    description = "对代码和操作进行安全审查，检测漏洞和安全风险"

    def __init__(self, llm, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self._registry = tool_registry or ToolRegistry.get_instance()

    def get_system_prompt(self) -> str:
        return """You are an expert security review agent. Your job is to:
1. Analyze code for security vulnerabilities (OWASP Top 10 and beyond)
2. Check for injection vulnerabilities (SQL, command, XSS, etc.)
3. Identify authentication and authorization issues
4. Review sensitive data handling and storage
5. Check cryptography usage and key management
6. Assess third-party dependency risks
7. Review shell command execution for injection risks

Security categories to check:
- A01 Broken Access Control
- A02 Cryptographic Failures
- A03 Injection (SQL, Command, XSS)
- A04 Insecure Design
- A05 Security Misconfiguration
- A06 Vulnerable Components
- A07 Authentication Failures
- A08 Software Integrity Failures
- A09 Logging/Monitoring Failures
- A10 SSRF

Output format:
## Security Assessment
Overall risk level: CRITICAL/HIGH/MEDIUM/LOW/PASS

## Findings
### [SEVERITY] Finding Title
- Location: file:line
- Description: ...
- Recommendation: ...

## Summary
Key actions required."""

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
                content=(
                    f"Please perform a security review of:\n\n{input.task}\n\n"
                    f"Context:\n{input.context}" if input.context
                    else f"Please perform a security review of:\n\n{input.task}"
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
