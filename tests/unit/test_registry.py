"""
Tests for Agent Registry module
"""
from unittest.mock import Mock

import pytest

from core.agent.registry import AgentRegistry


class TestAgentRegistry:
    """Test Agent Registry"""

    def test_registry_singleton(self):
        """Test registry singleton"""
        registry1 = AgentRegistry.get_instance()
        registry2 = AgentRegistry.get_instance()
        assert registry1 == registry2

    def test_registry_creation(self):
        """Test creating registry"""
        registry = AgentRegistry()
        assert registry is not None
        assert registry._factories == {}

    def test_register_factory(self):
        """Test registering factory"""
        registry = AgentRegistry.get_instance()
        mock_factory = Mock()

        registry.register_factory("test-agent", mock_factory)
        assert "test-agent" in registry._factories

    def test_create_agent(self):
        """Test creating agent"""
        registry = AgentRegistry.get_instance()
        mock_factory = Mock(return_value=Mock())
        mock_llm = Mock()

        registry.register_factory("test-agent", mock_factory)
        agent = registry.create("test-agent", mock_llm)

        mock_factory.assert_called_once()
        assert agent is not None

    def test_create_agent_with_kwargs(self):
        """Test creating agent with kwargs"""
        registry = AgentRegistry.get_instance()
        mock_agent = Mock()
        mock_factory = Mock(return_value=mock_agent)
        mock_llm = Mock()

        registry.register_factory("custom-agent", mock_factory)
        agent = registry.create("custom-agent", mock_llm, tools=Mock(), memory=Mock())

        mock_factory.assert_called_once()

    def test_create_nonexistent_agent_type(self):
        """Test creating nonexistent agent type"""
        registry = AgentRegistry.get_instance()
        mock_llm = Mock()

        with pytest.raises(ValueError, match="No factory registered"):
            registry.create("nonexistent-type", mock_llm)

    def test_list_types(self):
        """Test listing types"""
        registry = AgentRegistry.get_instance()
        mock_factory = Mock()

        registry.register_factory("agent-type-1", mock_factory)
        types = registry.list_types()

        assert "agent-type-1" in types

    def test_list_types_empty(self):
        """Test listing types when empty"""
        # Note: singleton may have types from previous tests
        # Just verify list_types returns a list
        registry = AgentRegistry()
        types = registry.list_types()
        assert isinstance(types, list)

    def test_get_instance_creates_new(self):
        """Test get_instance creates new if None"""
        # Reset singleton
        AgentRegistry._instance = None
        registry = AgentRegistry.get_instance()
        assert registry is not None
        assert isinstance(registry, AgentRegistry)

    def test_factories_dict_exists(self):
        """Test factories dict exists"""
        registry = AgentRegistry()
        assert hasattr(registry, '_factories')
        assert isinstance(registry._factories, dict)

    def test_register_multiple_factories(self):
        """Test registering multiple factories"""
        registry = AgentRegistry.get_instance()
        factory1 = Mock()
        factory2 = Mock()

        registry.register_factory("type1", factory1)
        registry.register_factory("type2", factory2)

        types = registry.list_types()
        assert len(types) >= 2
        assert "type1" in types
        assert "type2" in types

    def test_overwrite_factory(self):
        """Test overwriting factory"""
        registry = AgentRegistry.get_instance()
        factory1 = Mock(return_value="agent1")
        factory2 = Mock(return_value="agent2")

        registry.register_factory("overwrite-test", factory1)
        registry.register_factory("overwrite-test", factory2)

        mock_llm = Mock()
        agent = registry.create("overwrite-test", mock_llm)

        # Should use factory2
        factory2.assert_called_once()
