"""
子代理模块单元测试 - DEV-001
测试覆盖: ExploreAgent, PlanAgent, VerifyAgent, ReviewAgent, BatchAgent, BaseSubAgent
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.agent.sub_agents.base import (
    BaseSubAgent,
    SubAgentInput,
    SubAgentOutput,
)
from core.agent.sub_agents.batch import BatchAgent, BatchResult, BatchTask
from core.agent.sub_agents.explore import ExploreAgent
from core.agent.sub_agents.plan import PlanAgent
from core.agent.sub_agents.review import ReviewAgent
from core.agent.sub_agents.verify import VerifyAgent
from core.llm.base import (
    BaseLLMProvider,
    ChatChunk,
    ChatResponse,
    Message,
    Usage,
)
from tools.base import BaseTool, ToolRegistry

# ─── Mock LLM Provider ────────────────────────────────────────────────────────

class MockLLMProvider(BaseLLMProvider):
    """测试用 Mock LLM Provider"""

    def __init__(self, responses: list[ChatResponse] | None = None) -> None:
        super().__init__(model="mock-model")
        self._responses = responses or []
        self._call_count = 0

    def set_responses(self, responses: list[ChatResponse]) -> None:
        """设置预设响应"""
        self._responses = responses
        self._call_count = 0

    async def chat(
        self,
        messages,
        tools=None,
        system=None,
        max_tokens=4096,
        temperature=1.0,
        **kwargs
    ) -> ChatResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = ChatResponse(
                content="Default response",
                usage=Usage(input_tokens=10, output_tokens=20),
                finish_reason="end_turn"
            )
        self._call_count += 1
        return resp

    async def chat_stream(
        self,
        messages,
        tools=None,
        system=None,
        max_tokens=4096,
        temperature=1.0,
        **kwargs
    ):
        resp = await self.chat(messages, tools=tools, system=system)
        yield ChatChunk(content=resp.content, finish_reason=resp.finish_reason)

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


# ─── Mock Tool ────────────────────────────────────────────────────────────────

class MockTool(BaseTool):
    """测试用 Mock 工具"""

    name = "mock_tool"
    description = "A mock tool for testing"

    def get_schema(self) -> dict:
        """返回工具参数的 JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input parameter"}
            },
            "required": []
        }

    async def execute(self, ctx, **kwargs):
        """执行工具"""
        return {"success": True, "result": "mock result"}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    """创建 Mock LLM Provider"""
    return MockLLMProvider([
        ChatResponse(
            content="Test response content",
            usage=Usage(input_tokens=50, output_tokens=100),
            finish_reason="end_turn"
        )
    ])


@pytest.fixture
def tool_registry():
    """创建工具注册表"""
    registry = ToolRegistry()
    registry.register(MockTool())
    return registry


@pytest.fixture
def sub_agent_input():
    """创建子代理输入"""
    return SubAgentInput(
        task="Test task description",
        context="Additional context information",
        metadata={"key": "value"}
    )


# ─── BaseSubAgent Tests ───────────────────────────────────────────────────────

class TestSubAgentInput:
    """测试 SubAgentInput 数据模型"""

    def test_input_creation(self):
        """测试输入创建"""
        input = SubAgentInput(
            task="Write a function",
            context="Python project",
            metadata={"priority": "high"}
        )
        assert input.task == "Write a function"
        assert input.context == "Python project"
        assert input.metadata["priority"] == "high"

    def test_input_defaults(self):
        """测试输入默认值"""
        input = SubAgentInput(task="Simple task")
        assert input.context == ""
        assert input.metadata == {}

    def test_input_serialization(self):
        """测试输入序列化"""
        input = SubAgentInput(task="Task", context="Ctx")
        data = input.model_dump()
        assert "task" in data
        assert "context" in data


class TestSubAgentOutput:
    """测试 SubAgentOutput 数据模型"""

    def test_output_creation_success(self):
        """测试成功输出创建"""
        output = SubAgentOutput(
            agent_type="explore",
            result="Analysis complete",
            success=True,
            input_tokens=100,
            output_tokens=200
        )
        assert output.agent_type == "explore"
        assert output.success is True
        assert output.error is None

    def test_output_creation_failure(self):
        """测试失败输出创建"""
        output = SubAgentOutput(
            agent_type="plan",
            result="",
            success=False,
            error="LLM API error"
        )
        assert output.success is False
        assert output.error == "LLM API error"

    def test_output_defaults(self):
        """测试输出默认值"""
        output = SubAgentOutput(agent_type="test", result="result")
        assert output.success is True
        assert output.input_tokens == 0
        assert output.output_tokens == 0
        assert output.metadata == {}

    def test_output_serialization(self):
        """测试输出序列化"""
        output = SubAgentOutput(
            agent_type="verify",
            result="Passed",
            metadata={"checks": 5}
        )
        data = output.model_dump()
        assert data["agent_type"] == "verify"
        assert data["metadata"]["checks"] == 5


# ─── ExploreAgent Tests ───────────────────────────────────────────────────────

class TestExploreAgent:
    """测试 Explore Agent"""

    def test_agent_type(self, mock_llm):
        """测试代理类型"""
        agent = ExploreAgent(mock_llm)
        assert agent.agent_type == "explore"

    def test_description(self, mock_llm):
        """测试代理描述"""
        agent = ExploreAgent(mock_llm)
        assert "探索" in agent.description or "explore" in agent.description.lower()

    def test_system_prompt(self, mock_llm):
        """测试系统提示"""
        agent = ExploreAgent(mock_llm)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 0
        assert "exploration" in prompt.lower() or "explore" in prompt.lower()

    def test_get_tools(self, mock_llm, tool_registry):
        """测试工具获取"""
        agent = ExploreAgent(mock_llm, tool_registry)
        tools = agent.get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_run_success(self, mock_llm):
        """测试成功执行"""
        mock_llm.set_responses([
            ChatResponse(
                content="## Project Structure\n\n- src/\n- tests/\n- docs/",
                usage=Usage(input_tokens=50, output_tokens=100),
                finish_reason="end_turn"
            )
        ])
        agent = ExploreAgent(mock_llm)
        input = SubAgentInput(task="Explore the project structure")
        output = await agent.run(input)

        assert output.success is True
        assert output.agent_type == "explore"
        assert "Project Structure" in output.result
        assert output.input_tokens == 50
        assert output.output_tokens == 100

    @pytest.mark.asyncio
    async def test_run_with_context(self, mock_llm):
        """测试带上下文执行"""
        mock_llm.set_responses([
            ChatResponse(
                content="Analysis based on context",
                usage=Usage(input_tokens=100, output_tokens=150),
                finish_reason="end_turn"
            )
        ])
        agent = ExploreAgent(mock_llm)
        input = SubAgentInput(
            task="Find dependencies",
            context="Focus on core module"
        )
        output = await agent.run(input)

        assert output.success is True
        assert len(output.result) > 0

    @pytest.mark.asyncio
    async def test_run_llm_error(self, mock_llm):
        """测试 LLM 错误处理"""
        # 创建会抛出异常的 Mock
        error_llm = MockLLMProvider()
        error_llm.chat = AsyncMock(side_effect=Exception("API Error"))

        agent = ExploreAgent(error_llm)
        input = SubAgentInput(task="Test task")
        output = await agent.run(input)

        assert output.success is False
        assert "API Error" in output.error


# ─── PlanAgent Tests ──────────────────────────────────────────────────────────

class TestPlanAgent:
    """测试 Plan Agent"""

    def test_agent_type(self, mock_llm):
        """测试代理类型"""
        agent = PlanAgent(mock_llm)
        assert agent.agent_type == "plan"

    def test_system_prompt(self, mock_llm):
        """测试系统提示包含任务规划内容"""
        agent = PlanAgent(mock_llm)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 0
        assert "plan" in prompt.lower() or "task" in prompt.lower()

    def test_no_tools(self, mock_llm):
        """测试 Plan Agent 默认无工具"""
        agent = PlanAgent(mock_llm)
        tools = agent.get_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_run_task_decomposition(self, mock_llm):
        """测试任务分解"""
        mock_llm.set_responses([
            ChatResponse(
                content="""## Task Analysis
Implement user authentication

## Step-by-Step Plan
1. Design auth schema - S
2. Implement login - M
3. Add session management - M
4. Write tests - S

## Dependencies
- Step 2 depends on Step 1
- Step 4 depends on Step 2, 3""",
                usage=Usage(input_tokens=80, output_tokens=200),
                finish_reason="end_turn"
            )
        ])
        agent = PlanAgent(mock_llm)
        input = SubAgentInput(task="Implement user authentication")
        output = await agent.run(input)

        assert output.success is True
        assert "Step-by-Step Plan" in output.result
        assert "Dependencies" in output.result

    @pytest.mark.asyncio
    async def test_run_with_metadata(self, mock_llm):
        """测试带元数据执行"""
        mock_llm.set_responses([
            ChatResponse(
                content="Plan created",
                usage=Usage(input_tokens=50, output_tokens=100),
                finish_reason="end_turn"
            )
        ])
        agent = PlanAgent(mock_llm)
        input = SubAgentInput(
            task="Complex task",
            context="Previous context",
            metadata={"priority": "high", "deadline": "2024-12-31"}
        )
        output = await agent.run(input)

        assert output.success is True


# ─── VerifyAgent Tests ─────────────────────────────────────────────────────────

class TestVerifyAgent:
    """测试 Verify Agent"""

    def test_agent_type(self, mock_llm):
        """测试代理类型"""
        agent = VerifyAgent(mock_llm)
        assert agent.agent_type == "verify"

    def test_system_prompt(self, mock_llm):
        """测试系统提示包含验证内容"""
        agent = VerifyAgent(mock_llm)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 0
        assert "verify" in prompt.lower() or "verification" in prompt.lower()

    def test_get_tools(self, mock_llm, tool_registry):
        """测试工具获取"""
        agent = VerifyAgent(mock_llm, tool_registry)
        tools = agent.get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_run_verification(self, mock_llm):
        """测试代码验证"""
        mock_llm.set_responses([
            ChatResponse(
                content="""## Verification Report

### Correctness: PASS
- Code logic is correct
- Edge cases handled

### Security: PASS
- No SQL injection risks
- Input validation present

### Performance: WARNING
- Potential N+1 query issue

### Recommendations
- Add index on user_id column""",
                usage=Usage(input_tokens=100, output_tokens=150),
                finish_reason="end_turn"
            )
        ])
        agent = VerifyAgent(mock_llm)
        input = SubAgentInput(
            task="Verify the authentication module",
            context="File: auth.py, Lines: 1-100"
        )
        output = await agent.run(input)

        assert output.success is True
        assert "PASS" in output.result
        assert "Recommendations" in output.result

    @pytest.mark.asyncio
    async def test_run_with_error_detection(self, mock_llm):
        """测试错误检测"""
        mock_llm.set_responses([
            ChatResponse(
                content="""## Verification Report

### FAIL Issues:
1. Line 42: Unreachable code
2. Line 55: Potential null pointer exception

### Recommendations:
- Fix unreachable code block
- Add null check before access""",
                usage=Usage(input_tokens=80, output_tokens=120),
                finish_reason="end_turn"
            )
        ])
        agent = VerifyAgent(mock_llm)
        input = SubAgentInput(task="Verify buggy code")
        output = await agent.run(input)

        assert output.success is True
        assert "FAIL" in output.result


# ─── ReviewAgent Tests ─────────────────────────────────────────────────────────

class TestReviewAgent:
    """测试 Review Agent"""

    def test_agent_type(self, mock_llm):
        """测试代理类型"""
        agent = ReviewAgent(mock_llm)
        assert agent.agent_type == "review"

    def test_system_prompt(self, mock_llm):
        """测试系统提示包含审查内容"""
        agent = ReviewAgent(mock_llm)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 0
        assert "review" in prompt.lower() or "code" in prompt.lower()

    @pytest.mark.asyncio
    async def test_run_code_review(self, mock_llm):
        """测试代码审查"""
        mock_llm.set_responses([
            ChatResponse(
                content="""## Code Review Summary

### Critical Issues: 0
### Warnings: 2
1. Missing docstring on public function
2. Variable naming could be improved

### Suggestions: 3
- Consider using type hints
- Add unit tests
- Refactor long function

### Best Practices Observed
- Good error handling
- Proper logging""",
                usage=Usage(input_tokens=100, output_tokens=200),
                finish_reason="end_turn"
            )
        ])
        agent = ReviewAgent(mock_llm)
        input = SubAgentInput(
            task="Review PR #42",
            context="Changes in api/handlers.py",
            metadata={"review_type": "pr"}
        )
        output = await agent.run(input)

        assert output.success is True
        assert "Warnings" in output.result
        assert output.metadata.get("review_type") == "pr"

    @pytest.mark.asyncio
    async def test_run_security_review(self, mock_llm):
        """测试安全审查"""
        mock_llm.set_responses([
            ChatResponse(
                content="""## Security Review

### Security Issues Found: 1
- Line 23: Potential SQL injection

### Recommendations:
- Use parameterized queries
- Add input sanitization""",
                usage=Usage(input_tokens=50, output_tokens=80),
                finish_reason="end_turn"
            )
        ])
        agent = ReviewAgent(mock_llm)
        input = SubAgentInput(
            task="Security review of database module",
            metadata={"review_type": "security"}
        )
        output = await agent.run(input)

        assert output.success is True
        assert "Security" in output.result


# ─── BatchAgent Tests ──────────────────────────────────────────────────────────

class TestBatchAgent:
    """测试 Batch Agent"""

    def test_agent_type(self, mock_llm):
        """测试代理类型"""
        agent = BatchAgent(mock_llm)
        assert agent.agent_type == "batch"

    def test_constants(self, mock_llm):
        """测试批量处理限制常量"""
        agent = BatchAgent(mock_llm)
        assert agent.MAX_CONCURRENT_TASKS == 5
        assert agent.MAX_BATCH_SIZE == 20

    def test_system_prompt(self, mock_llm):
        """测试系统提示"""
        agent = BatchAgent(mock_llm)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 0
        assert "batch" in prompt.lower() or "parallel" in prompt.lower()

    @pytest.mark.asyncio
    async def test_run_empty_batch(self, mock_llm):
        """测试空批量任务（实际会创建默认单一任务）"""
        agent = BatchAgent(mock_llm)
        input = SubAgentInput(task="Batch process", metadata={"tasks": []})
        output = await agent.run(input)
        # 空任务列表会自动创建默认任务，所以返回success=True
        assert output.success is True
        assert "single" in output.result or "Success: 1" in output.result

    @pytest.mark.asyncio
    async def test_run_single_task(self, mock_llm):
        """测试单个批量任务"""
        mock_llm.set_responses([
            ChatResponse(
                content="Task 1 completed successfully",
                usage=Usage(input_tokens=30, output_tokens=50),
                finish_reason="end_turn"
            )
        ])
        agent = BatchAgent(mock_llm)
        input = SubAgentInput(
            task="Process batch",
            metadata={
                "tasks": [
                    {"task_id": "t1", "task": "Analyze file A"}
                ]
            }
        )
        output = await agent.run(input)

        # 批量代理应该处理任务
        assert output.agent_type == "batch"

    @pytest.mark.asyncio
    async def test_run_multiple_tasks(self, mock_llm):
        """测试多任务批量处理"""
        # 为每个任务准备响应
        mock_llm.set_responses([
            ChatResponse(
                content=f"Task {i} result",
                usage=Usage(input_tokens=20, output_tokens=30),
                finish_reason="end_turn"
            )
            for i in range(3)
        ])
        agent = BatchAgent(mock_llm)
        input = SubAgentInput(
            task="Batch analysis",
            metadata={
                "tasks": [
                    {"task_id": "t1", "task": "Analyze A"},
                    {"task_id": "t2", "task": "Analyze B"},
                    {"task_id": "t3", "task": "Analyze C"},
                ]
            }
        )
        output = await agent.run(input)

        assert output.agent_type == "batch"


class TestBatchTask:
    """测试 BatchTask 数据模型"""

    def test_batch_task_creation(self):
        """测试批量任务创建"""
        task = BatchTask(
            task_id="task_001",
            task="Process file",
            context="File path: /src/main.py",
            priority=1
        )
        assert task.task_id == "task_001"
        assert task.priority == 1

    def test_batch_task_defaults(self):
        """测试批量任务默认值"""
        task = BatchTask(task_id="t1", task="Task")
        assert task.context == ""
        assert task.priority == 0


class TestBatchResult:
    """测试 BatchResult 数据模型"""

    def test_batch_result_success(self):
        """测试批量结果成功"""
        result = BatchResult(
            task_id="t1",
            success=True,
            result="Completed",
            duration_ms=100
        )
        assert result.success is True
        assert result.error is None

    def test_batch_result_failure(self):
        """测试批量结果失败"""
        result = BatchResult(
            task_id="t2",
            success=False,
            result="",
            error="Timeout",
            duration_ms=5000
        )
        assert result.success is False
        assert result.error == "Timeout"


# ─── BaseSubAgent Abstract Tests ───────────────────────────────────────────────

class TestBaseSubAgent:
    """测试 BaseSubAgent 基类"""

    def test_cannot_instantiate_directly(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseSubAgent(mock_llm)

    @pytest.mark.asyncio
    async def test_llm_call_helper(self, mock_llm):
        """测试 _call_llm 辅助方法"""
        mock_llm.set_responses([
            ChatResponse(
                content="Response from LLM",
                usage=Usage(input_tokens=50, output_tokens=100),
                finish_reason="end_turn"
            )
        ])
        agent = ExploreAgent(mock_llm)
        messages = [Message(role="user", content="Test")]

        content, in_tok, out_tok = await agent._call_llm(messages)

        assert content == "Response from LLM"
        assert in_tok == 50
        assert out_tok == 100


# ─── Integration Tests ─────────────────────────────────────────────────────────

class TestSubAgentIntegration:
    """子代理集成测试"""

    @pytest.mark.asyncio
    async def test_explore_to_verify_chain(self, mock_llm):
        """测试 Explore -> Verify 链式调用"""
        # Explore 响应
        mock_llm.set_responses([
            ChatResponse(
                content="Found 3 potential issues in the code",
                usage=Usage(input_tokens=50, output_tokens=80),
                finish_reason="end_turn"
            ),
            # Verify 响应
            ChatResponse(
                content="Verification: 2 issues confirmed",
                usage=Usage(input_tokens=60, output_tokens=100),
                finish_reason="end_turn"
            )
        ])

        explore = ExploreAgent(mock_llm)
        verify = VerifyAgent(mock_llm)

        # 第一步：探索
        explore_output = await explore.run(
            SubAgentInput(task="Find issues in module X")
        )
        assert explore_output.success is True

        # 第二步：验证
        verify_output = await verify.run(
            SubAgentInput(
                task="Verify the findings",
                context=explore_output.result
            )
        )
        assert verify_output.success is True

    @pytest.mark.asyncio
    async def test_plan_then_review(self, mock_llm):
        """测试 Plan -> Review 链式调用"""
        mock_llm.set_responses([
            ChatResponse(
                content="## Plan\n1. Step A\n2. Step B\n3. Step C",
                usage=Usage(input_tokens=40, output_tokens=60),
                finish_reason="end_turn"
            ),
            ChatResponse(
                content="## Review\nPlan is feasible with minor adjustments",
                usage=Usage(input_tokens=50, output_tokens=80),
                finish_reason="end_turn"
            )
        ])

        plan = PlanAgent(mock_llm)
        review = ReviewAgent(mock_llm)

        plan_output = await plan.run(SubAgentInput(task="Plan feature X"))
        assert plan_output.success is True

        review_output = await review.run(
            SubAgentInput(
                task="Review the plan",
                context=plan_output.result
            )
        )
        assert review_output.success is True


# ─── Edge Cases and Error Handling ─────────────────────────────────────────────

class TestSubAgentEdgeCases:
    """边界情况和错误处理测试"""

    @pytest.mark.asyncio
    async def test_empty_task(self, mock_llm):
        """测试空任务"""
        agent = ExploreAgent(mock_llm)
        input = SubAgentInput(task="")
        output = await agent.run(input)

        # 应该正常处理，不崩溃
        assert output.agent_type == "explore"

    @pytest.mark.asyncio
    async def test_very_long_task(self, mock_llm):
        """测试超长任务描述"""
        mock_llm.set_responses([
            ChatResponse(
                content="Processed",
                usage=Usage(input_tokens=1000, output_tokens=100),
                finish_reason="end_turn"
            )
        ])
        agent = PlanAgent(mock_llm)
        long_task = "A" * 5000  # 5000字符的长任务
        input = SubAgentInput(task=long_task)
        output = await agent.run(input)

        assert output.success is True

    @pytest.mark.asyncio
    async def test_special_characters_in_task(self, mock_llm):
        """测试任务中的特殊字符"""
        mock_llm.set_responses([
            ChatResponse(
                content="Handled special chars",
                usage=Usage(input_tokens=50, output_tokens=50),
                finish_reason="end_turn"
            )
        ])
        agent = VerifyAgent(mock_llm)
        input = SubAgentInput(
            task="Verify code with special chars: <>&\"'${variable}",
            context="Unicode: 中文 日本語 한국어"
        )
        output = await agent.run(input)

        assert output.success is True

    @pytest.mark.asyncio
    async def test_llm_timeout_handling(self, mock_llm):
        """测试 LLM 超时处理"""
        # 创建超时的 Mock
        timeout_llm = MockLLMProvider()
        timeout_llm.chat = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))

        agent = ExploreAgent(timeout_llm)
        input = SubAgentInput(task="Test timeout")
        output = await agent.run(input)

        assert output.success is False
        assert "Timeout" in output.error or output.error is not None

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, mock_llm):
        """测试瞬时错误的处理"""
        # 第一次失败，第二次成功
        call_count = 0

        async def flaky_chat(*args, **kwargs):
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return ChatResponse(
                content="Success after retry",
                usage=Usage(input_tokens=50, output_tokens=50),
                finish_reason="end_turn"
            )

        flaky_llm = MockLLMProvider()
        flaky_llm.chat = flaky_chat

        agent = PlanAgent(flaky_llm)
        input = SubAgentInput(task="Test retry")
        output = await agent.run(input)

        # 当前实现不自动重试，应该返回错误
        assert output.success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
