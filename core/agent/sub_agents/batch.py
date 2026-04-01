"""
Batch Agent - 批量任务处理子代理
"""
from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from core.llm.base import Message, ToolDefinition
from tools.base import ToolRegistry

from .base import BaseSubAgent, SubAgentInput, SubAgentOutput


class BatchTask(BaseModel):
    """单个批量任务"""
    task_id: str
    task: str
    context: str = ""
    priority: int = 0


class BatchResult(BaseModel):
    """单个批量任务结果"""
    task_id: str
    success: bool
    result: str
    error: str | None = None
    duration_ms: int = 0


class BatchAgent(BaseSubAgent):
    """批量代理：并行处理多个相似任务，优化执行效率"""

    agent_type = "batch"
    description = "批量处理多个相似任务，支持并行执行和任务聚合"

    # 批量处理限制
    MAX_CONCURRENT_TASKS = 5
    MAX_BATCH_SIZE = 20

    def __init__(self, llm, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self._registry = tool_registry or ToolRegistry.get_instance()

    def get_system_prompt(self) -> str:
        return """You are an efficient batch processing agent. Your responsibilities include:

1. Task Analysis
   - Understand the common pattern across batch tasks
   - Identify shared context and resources
   - Determine optimal processing order

2. Parallel Execution Strategy
   - Identify independent tasks that can run concurrently
   - Group related tasks for efficient processing
   - Handle dependencies between tasks

3. Result Aggregation
   - Consolidate results from all tasks
   - Identify patterns and common findings
   - Provide summary statistics and key insights

4. Error Handling
   - Handle individual task failures gracefully
   - Provide partial results when some tasks fail
   - Report which tasks succeeded/failed

Process tasks efficiently while maintaining quality and accuracy.
Provide clear, structured output with:
- Total tasks processed
- Success/failure counts
- Aggregated findings
- Individual task details (if significant)"""

    def get_tools(self) -> list[ToolDefinition]:
        return [
            t.to_definition()
            for t in self._registry.get_all()
            if t.name in ("read_file", "execute_shell_command", "glob_search", "grep_search")
        ]

    async def run(self, input: SubAgentInput) -> SubAgentOutput:
        """执行批量任务"""
        # 解析批量任务
        tasks = self._parse_batch_tasks(input)

        if not tasks:
            return SubAgentOutput(
                agent_type=self.agent_type,
                result="No valid tasks found in batch input.",
                success=False,
                error="Empty task list",
            )

        # 限制批量大小
        if len(tasks) > self.MAX_BATCH_SIZE:
            tasks = tasks[:self.MAX_BATCH_SIZE]

        try:
            # 并行执行任务
            results = await self._execute_batch(tasks, input)

            # 聚合结果
            aggregated = self._aggregate_results(results)

            return SubAgentOutput(
                agent_type=self.agent_type,
                result=aggregated,
                success=True,
                metadata={
                    "total_tasks": len(tasks),
                    "successful": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                },
            )
        except Exception as e:
            return SubAgentOutput(
                agent_type=self.agent_type,
                result="",
                success=False,
                error=str(e),
            )

    def _parse_batch_tasks(self, input: SubAgentInput) -> list[dict[str, Any]]:
        """解析批量任务列表"""
        tasks = input.metadata.get("tasks", [])
        if not tasks:
            # 尝试从任务描述中解析
            tasks = [{"task_id": "single", "task": input.task, "context": input.context}]
        return tasks[:self.MAX_BATCH_SIZE]

    async def _execute_batch(self, tasks: list[dict], input: SubAgentInput) -> list[BatchResult]:
        """并行执行批量任务"""
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TASKS)

        async def execute_single(task_data: dict) -> BatchResult:
            async with semaphore:
                return await self._execute_single_task(task_data)

        results = await asyncio.gather(
            *[execute_single(t) for t in tasks],
            return_exceptions=True,
        )

        # 处理异常结果
        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(BatchResult(
                    task_id=tasks[i].get("task_id", str(i)),
                    success=False,
                    result="",
                    error=str(r),
                ))
            else:
                final_results.append(r)

        return final_results

    async def _execute_single_task(self, task_data: dict) -> BatchResult:
        """执行单个任务"""
        import time
        start = time.monotonic()

        task_id = task_data.get("task_id", "unknown")
        task = task_data.get("task", "")
        context = task_data.get("context", "")

        messages = [
            Message(
                role="user",
                content=f"Task: {task}\n\nContext: {context}" if context else f"Task: {task}",
            )
        ]

        try:
            content, _, _ = await self._call_llm(messages, max_tokens=2048)
            duration_ms = int((time.monotonic() - start) * 1000)
            return BatchResult(
                task_id=task_id,
                success=True,
                result=content,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return BatchResult(
                task_id=task_id,
                success=False,
                result="",
                error=str(e),
                duration_ms=duration_ms,
            )

    def _aggregate_results(self, results: list[BatchResult]) -> str:
        """聚合批量结果"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        summary = f"""Batch Processing Complete
{'=' * 50}
Total: {len(results)} | Success: {len(successful)} | Failed: {len(failed)}

"""
        if successful:
            summary += "Successful Results:\n"
            for r in successful:
                summary += f"  [{r.task_id}] {r.result[:100]}...\n" if len(r.result) > 100 else f"  [{r.task_id}] {r.result}\n"

        if failed:
            summary += "\nFailed Tasks:\n"
            for r in failed:
                summary += f"  [{r.task_id}] Error: {r.error}\n"

        return summary
