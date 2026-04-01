"""
主代理单元测试 - DEV-001（使用 Mock LLM）
"""
from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.agent.coordinator import AgentCoordinator
from core.agent.main_agent import MainAgent
from core.llm.base import (
    BaseLLMProvider,
    ChatChunk,
    ChatResponse,
    Message,
    ToolUseBlock,
)
from tools import register_default_tools
from tools.base import ToolRegistry

# ─── Mock LLM ────────────────────────────────────────────────────────────────

class MockLLMProvider(BaseLLMProvider):
    """测试用 Mock LLM，返回预设响应"""

    def __init__(self, responses: list[ChatResponse]) -> None:
        super().__init__(model="mock-model")
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, tools=None, system=None, max_tokens=4096, temperature=1.0, **kwargs) -> ChatResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = ChatResponse(content="Done.", finish_reason="end_turn")
        self._call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None, system=None, max_tokens=4096, temperature=1.0, **kwargs) -> AsyncIterator[ChatChunk]:
        resp = await self.chat(messages, tools=tools, system=system, max_tokens=max_tokens)
        yield ChatChunk(content=resp.content, finish_reason=resp.finish_reason)

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def registry():
    reg = ToolRegistry()
    return register_default_tools(reg)


@pytest.fixture
def simple_llm():
    return MockLLMProvider([
        ChatResponse(content="Hello! I'm CoPaw Code.", finish_reason="end_turn"),
    ])


@pytest.fixture
def tool_calling_llm():
    """模拟调用工具的 LLM：先调用工具，再给出最终答案"""
    return MockLLMProvider([
        # 第一轮：调用 execute_shell_command
        ChatResponse(
            content="",
            tool_uses=[ToolUseBlock(id="call_1", name="execute_shell_command", input={"command": "echo hello"})],
            finish_reason="tool_use",
        ),
        # 第二轮：给出最终文本响应
        ChatResponse(content="The command output was: hello", finish_reason="end_turn"),
    ])


# ─── MainAgent Tests ──────────────────────────────────────────────────────────

class TestMainAgent:
    @pytest.mark.asyncio
    async def test_simple_chat(self, simple_llm, registry):
        agent = MainAgent(llm=simple_llm, tool_registry=registry)
        messages = [Message(role="user", content="Hello!")]
        text, tool_results = await agent.chat(messages)
        assert "CoPaw Code" in text
        assert tool_results == []

    @pytest.mark.asyncio
    async def test_tool_use_cycle(self, tool_calling_llm, registry):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = MainAgent(
                llm=tool_calling_llm,
                tool_registry=registry,
                working_dir=tmpdir,
            )
            messages = [Message(role="user", content="Run echo hello")]
            text, tool_results = await agent.chat(messages)

            # 验证工具被调用
            assert len(tool_results) == 1
            assert tool_results[0].tool_name == "execute_shell_command"
            assert tool_results[0].success

            # 验证最终响应包含工具结果的引用
            assert "hello" in text

    @pytest.mark.asyncio
    async def test_stream_events(self, simple_llm, registry):
        agent = MainAgent(llm=simple_llm, tool_registry=registry)
        messages = [Message(role="user", content="Hello")]

        events = []
        async for event in agent.chat_stream(messages):
            events.append(event)

        event_types = [e.event_type for e in events]
        assert "text" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_max_iterations_guard(self, registry):
        """验证最大迭代次数保护"""
        # 无限循环调用工具的 LLM
        infinite_llm = MockLLMProvider([
            ChatResponse(
                content="",
                tool_uses=[ToolUseBlock(id=f"call_{i}", name="execute_shell_command", input={"command": "echo loop"})],
                finish_reason="tool_use",
            )
            for i in range(30)  # 超过 max_iterations
        ])

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = MainAgent(
                llm=infinite_llm,
                tool_registry=registry,
                max_iterations=3,
                working_dir=tmpdir,
            )
            messages = [Message(role="user", content="Loop forever")]
            text, tool_results = await agent.chat(messages)
            assert "Warning" in text or len(tool_results) <= 3


# ─── AgentCoordinator Tests ───────────────────────────────────────────────────

class TestAgentCoordinator:
    @pytest.mark.asyncio
    async def test_invoke_unknown_agent(self, registry):
        llm = MockLLMProvider([])
        coordinator = AgentCoordinator(llm=llm, tool_registry=registry)
        output = await coordinator.invoke("nonexistent", "some task")
        assert not output.success
        assert "Unknown agent type" in output.error

    @pytest.mark.asyncio
    async def test_invoke_plan_agent(self, registry):
        llm = MockLLMProvider([
            ChatResponse(content="## Plan\n1. Step one\n2. Step two", finish_reason="end_turn"),
        ])
        coordinator = AgentCoordinator(llm=llm, tool_registry=registry)
        output = await coordinator.invoke("plan", "Build a REST API")
        assert output.success
        assert output.agent_type == "plan"
        assert "Plan" in output.result

    def test_list_agents(self, registry):
        llm = MockLLMProvider([])
        coordinator = AgentCoordinator(llm=llm, tool_registry=registry)
        agents = coordinator.list_agents()
        types = [a["type"] for a in agents]
        assert "explore" in types
        assert "plan" in types
        assert "verify" in types

    def test_aggregate_results(self, registry):
        from core.agent.sub_agents.base import SubAgentOutput
        llm = MockLLMProvider([])
        coordinator = AgentCoordinator(llm=llm, tool_registry=registry)
        outputs = [
            SubAgentOutput(agent_type="plan", result="Step 1, Step 2", success=True),
            SubAgentOutput(agent_type="verify", result="All good", success=True),
        ]
        aggregated = coordinator.aggregate_results(outputs)
        assert "PLAN" in aggregated
        assert "VERIFY" in aggregated
        assert "Step 1" in aggregated
