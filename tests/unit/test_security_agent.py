"""
Tests for Security Sub-Agent module
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.agent.sub_agents.base import SubAgentInput, SubAgentOutput
from core.agent.sub_agents.security import SecurityAgent


class TestSecurityAgent:
    """Test Security Agent"""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM provider"""
        llm = Mock()
        llm.generate = AsyncMock(return_value=(Mock(content="Security analysis"), 100, 50))
        return llm

    @pytest.fixture
    def mock_tool_registry(self):
        """Create mock tool registry"""
        registry = Mock()
        tool1 = Mock()
        tool1.name = "read_file"
        tool1.to_definition = Mock(return_value=Mock())
        tool2 = Mock()
        tool2.name = "grep_search"
        tool2.to_definition = Mock(return_value=Mock())
        registry.get_all = Mock(return_value=[tool1, tool2])
        registry.get_instance = Mock(return_value=registry)
        return registry

    @pytest.fixture
    def security_agent(self, mock_llm, mock_tool_registry):
        """Create security agent"""
        with patch('tools.base.ToolRegistry.get_instance', return_value=mock_tool_registry):
            agent = SecurityAgent(llm=mock_llm, tool_registry=mock_tool_registry)
            return agent

    def test_security_agent_creation(self, security_agent):
        """Test creating security agent"""
        assert security_agent is not None
        assert security_agent.llm is not None

    def test_security_agent_type(self, security_agent):
        """Test security agent type"""
        assert security_agent.agent_type == "security"

    def test_security_agent_description(self, security_agent):
        """Test security agent description"""
        assert security_agent.description is not None
        assert "安全" in security_agent.description or "security" in security_agent.description.lower()

    def test_get_system_prompt(self, security_agent):
        """Test get system prompt"""
        prompt = security_agent.get_system_prompt()
        assert prompt is not None
        assert "security" in prompt.lower()
        assert len(prompt) > 100

    def test_get_tools(self, security_agent):
        """Test get tools"""
        tools = security_agent.get_tools()
        assert tools is not None
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_security_agent_run(self, security_agent, mock_llm):
        """Test security agent run"""
        # Mock _call_llm to return content, input_tokens, output_tokens
        security_agent._call_llm = AsyncMock(return_value=("Security report", 100, 50))

        input_data = SubAgentInput(task="Review this code", context="Test context")
        result = await security_agent.run(input_data)

        assert result is not None
        assert result.agent_type == "security"
        assert result.success is True
        assert result.result == "Security report"

    @pytest.mark.asyncio
    async def test_security_agent_run_with_context(self, security_agent):
        """Test security agent run with context"""
        security_agent._call_llm = AsyncMock(return_value=("Analysis complete", 200, 100))

        input_data = SubAgentInput(
            task="Check file /app/main.py",
            context="File contains sensitive operations"
        )
        result = await security_agent.run(input_data)

        assert result.success is True
        assert result.input_tokens == 200
        assert result.output_tokens == 100

    @pytest.mark.asyncio
    async def test_security_agent_run_error(self, security_agent):
        """Test security agent run with error"""
        security_agent._call_llm = AsyncMock(side_effect=Exception("LLM error"))

        input_data = SubAgentInput(task="Review code")
        result = await security_agent.run(input_data)

        assert result.success is False
        assert result.error == "LLM error"

    def test_agent_type_attribute(self, security_agent):
        """Test agent type attribute"""
        assert SecurityAgent.agent_type == "security"

    def test_description_attribute(self, security_agent):
        """Test description attribute"""
        assert SecurityAgent.description is not None


class TestSecurityAgentWithRealRegistry:
    """Test Security Agent with real registry"""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM"""
        llm = Mock()
        llm.generate = AsyncMock(return_value=(Mock(content="Response"), 100, 50))
        return llm

    @pytest.mark.asyncio
    async def test_agent_creation_without_registry(self, mock_llm):
        """Test agent creation without explicit registry"""
        with patch('tools.base.ToolRegistry.get_instance') as mock_get_instance:
            mock_registry = Mock()
            mock_registry.get_all = Mock(return_value=[])
            mock_get_instance.return_value = mock_registry

            agent = SecurityAgent(llm=mock_llm)
            assert agent is not None

    @pytest.mark.asyncio
    async def test_agent_run_minimal(self, mock_llm):
        """Test agent run minimal input"""
        with patch('tools.base.ToolRegistry.get_instance') as mock_get_instance:
            mock_registry = Mock()
            mock_registry.get_all = Mock(return_value=[])
            mock_get_instance.return_value = mock_registry

            agent = SecurityAgent(llm=mock_llm)
            agent._call_llm = AsyncMock(return_value=("OK", 10, 5))

            input_data = SubAgentInput(task="test")
            result = await agent.run(input_data)

            assert result is not None


class TestSubAgentInputOutput:
    """Test SubAgentInput and SubAgentOutput"""

    def test_sub_agent_input_creation(self):
        """Test SubAgentInput creation"""
        input_data = SubAgentInput(task="Test task")
        assert input_data.task == "Test task"
        # context defaults to empty string
        assert input_data.context == ""

    def test_sub_agent_input_with_context(self):
        """Test SubAgentInput with context"""
        input_data = SubAgentInput(task="Test", context="Some context")
        assert input_data.context == "Some context"

    def test_sub_agent_output_creation(self):
        """Test SubAgentOutput creation"""
        output = SubAgentOutput(
            agent_type="security",
            result="Result text",
            success=True,
            input_tokens=100,
            output_tokens=50
        )
        assert output.agent_type == "security"
        assert output.result == "Result text"
        assert output.success is True

    def test_sub_agent_output_error(self):
        """Test SubAgentOutput with error"""
        output = SubAgentOutput(
            agent_type="security",
            result="",
            success=False,
            error="Something went wrong"
        )
        assert output.success is False
        assert output.error == "Something went wrong"
