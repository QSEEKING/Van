"""
Plan Agent - 任务规划和分解子代理
"""
from __future__ import annotations

from core.llm.base import Message

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class PlanAgent(BaseSubAgent):
    """计划代理：任务分解、步骤规划、风险评估"""

    agent_type = "plan"
    description = "将复杂任务分解为可执行的步骤序列，并评估潜在风险"

    def get_system_prompt(self) -> str:
        return """You are an expert task planning agent. Your job is to:
1. Analyze complex development tasks and break them into clear, actionable steps
2. Identify dependencies between steps
3. Estimate effort and potential risks for each step
4. Suggest the optimal execution order
5. Flag potential blockers or unknowns

Output format:
## Task Analysis
Brief description of what needs to be done

## Step-by-Step Plan
1. [Step name] - [Brief description] - [Estimated effort: XS/S/M/L/XL]
2. ...

## Dependencies
- Step N depends on Step M because...

## Risks & Unknowns
- Risk: ... | Mitigation: ...

## Success Criteria
- How to verify the task is complete

Be specific, practical, and realistic."""

    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        messages = [
            Message(
                role="user",
                content=(
                    f"Please create a detailed plan for the following task:\n\n"
                    f"{input.task}\n\n"
                    f"Context:\n{input.context}" if input.context
                    else f"Please create a detailed plan for the following task:\n\n{input.task}"
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
