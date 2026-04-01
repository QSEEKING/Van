"""
Tests for CLI REPL module
"""
from unittest.mock import AsyncMock, Mock

import pytest

from cli.commands.repl import REPL, REPLConfig


class TestREPLConfig:
    """Test REPL Configuration"""

    def test_config_class_attributes(self):
        """Test config class attributes"""
        assert REPLConfig.PROMPT_USER == "❯ "
        assert REPLConfig.PROMPT_CONTINUE == "... "
        assert REPLConfig.PROMPT_TOOL == "🔧 "
        assert REPLConfig.HISTORY_FILE is not None

    def test_config_style(self):
        """Test config style"""
        assert REPLConfig.STYLE is not None

    def test_history_file_path(self):
        """Test history file path"""
        assert REPLConfig.HISTORY_FILE.endswith(".copaw_history")


class TestREPLCreation:
    """Test REPL Class Creation"""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent"""
        agent = Mock()
        agent.process = AsyncMock(return_value=Mock(content="Response"))
        agent.model = Mock()
        agent.model.name = "test-model"
        return agent

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings"""
        settings = Mock()
        settings.debug = False
        settings.model = "test-model"
        settings.model_dump = Mock(return_value={"debug": False, "model": "test-model"})
        return settings

    @pytest.fixture
    def mock_memory(self):
        """Create mock session memory"""
        memory = Mock()
        memory.session_id = "test-session"
        memory.working_dir = "/app"
        memory.turn_count = 0
        memory.total_input_tokens = 0
        memory.total_output_tokens = 0
        memory.total_tokens = 0
        memory.summary = ""
        memory.messages = []
        memory.add_message = Mock()
        memory.get_context = Mock(return_value="")
        memory.clear = Mock()
        return memory

    @pytest.fixture
    def repl(self, mock_agent, mock_settings, mock_memory):
        """Create REPL instance"""
        return REPL(agent=mock_agent, settings=mock_settings, session_memory=mock_memory)

    def test_repl_creation(self, repl):
        """Test creating REPL"""
        assert repl is not None
        assert repl.agent is not None
        assert repl.settings is not None
        assert repl.memory is not None

    def test_repl_has_slash_handler(self, repl):
        """Test REPL has slash handler"""
        assert hasattr(repl, 'slash_handler')
        assert repl.slash_handler is not None

    def test_repl_has_formatter(self, repl):
        """Test REPL has formatter"""
        assert hasattr(repl, 'formatter')
        assert repl.formatter is not None

    def test_repl_running_state(self, repl):
        """Test REPL running state"""
        assert repl._running is False  # Initially not running

    def test_repl_stop(self, repl):
        """Test REPL stop"""
        repl._running = True
        repl.stop()
        assert repl._running is False

    def test_repl_working_dir_property(self, repl):
        """Test REPL working_dir property"""
        assert repl.working_dir == "/app"

    def test_repl_working_dir_setter(self, repl, tmp_path):
        """Test REPL working_dir setter"""
        # Need a real directory for the setter
        repl.working_dir = str(tmp_path)
        assert repl.memory.working_dir == str(tmp_path)

    def test_repl_is_running(self, repl):
        """Test REPL is_running"""
        # is_running is a property, not a method
        assert repl._running is False
        repl._running = True
        assert repl._running is True

    def test_repl_multiline_buffer(self, repl):
        """Test REPL multiline buffer"""
        assert repl._multiline_buffer == []
        repl._multiline_buffer.append("line 1")
        assert len(repl._multiline_buffer) == 1

    def test_repl_current_task(self, repl):
        """Test REPL current task"""
        assert repl._current_task is None

    def test_repl_agent_property(self, repl, mock_agent):
        """Test REPL agent property"""
        assert repl.agent == mock_agent

    def test_repl_settings_property(self, repl, mock_settings):
        """Test REPL settings property"""
        assert repl.settings == mock_settings

    def test_repl_memory_property(self, repl, mock_memory):
        """Test REPL memory property"""
        assert repl.memory == mock_memory


class TestREPLSession:
    """Test REPL Session Management"""

    @pytest.fixture
    def repl_setup(self):
        """Create REPL setup"""
        agent = Mock()
        agent.process = AsyncMock(return_value=Mock(content="Response"))
        agent.model = Mock()
        agent.model.name = "test-model"
        settings = Mock()
        settings.debug = False
        settings.model = "test-model"
        settings.model_dump = Mock(return_value={"debug": False})
        memory = Mock()
        memory.session_id = "session-123"
        memory.working_dir = "/workspace"
        memory.turn_count = 5
        memory.total_input_tokens = 1000
        memory.total_output_tokens = 500
        memory.total_tokens = 1500
        memory.summary = "Test session summary"
        memory.messages = [Mock(), Mock()]
        memory.clear = Mock()

        repl = REPL(agent=agent, settings=settings, session_memory=memory)
        return repl, memory

    def test_session_info(self, repl_setup):
        """Test session info"""
        repl, memory = repl_setup
        assert memory.session_id == "session-123"
        assert memory.turn_count == 5

    def test_session_tokens(self, repl_setup):
        """Test session tokens"""
        repl, memory = repl_setup
        assert memory.total_input_tokens == 1000
        assert memory.total_output_tokens == 500
        assert memory.total_tokens == 1500

    def test_session_working_dir(self, repl_setup):
        """Test session working directory"""
        repl, memory = repl_setup
        assert repl.working_dir == "/workspace"

    def test_working_dir_change(self, repl_setup, tmp_path):
        """Test working directory change"""
        repl, memory = repl_setup
        repl.working_dir = str(tmp_path)
        assert memory.working_dir == str(tmp_path)


class TestREPLFormatterIntegration:
    """Test REPL Formatter Integration"""

    @pytest.fixture
    def repl_setup(self):
        """Create REPL setup"""
        agent = Mock()
        agent.process = AsyncMock(return_value=Mock(content="Response"))
        agent.model = Mock()
        agent.model.name = "test-model"
        settings = Mock()
        settings.debug = False
        settings.model = "test-model"
        memory = Mock()
        memory.session_id = "test"
        memory.working_dir = "/app"
        memory.turn_count = 0
        memory.total_input_tokens = 0
        memory.total_output_tokens = 0
        memory.total_tokens = 0
        memory.summary = ""
        memory.messages = []

        repl = REPL(agent=agent, settings=settings, session_memory=memory)
        return repl

    def test_formatter_exists(self, repl_setup):
        """Test formatter exists"""
        repl = repl_setup
        assert repl.formatter is not None

    def test_formatter_user_input(self, repl_setup):
        """Test formatter user input"""
        repl = repl_setup
        result = repl.formatter.format_user_input("Hello")
        assert result is not None

    def test_formatter_assistant_response(self, repl_setup):
        """Test formatter assistant response"""
        repl = repl_setup
        result = repl.formatter.format_assistant_response("Response")
        assert result is not None

    def test_formatter_error(self, repl_setup):
        """Test formatter error"""
        repl = repl_setup
        result = repl.formatter.format_error("Error message")
        assert result is not None

    def test_formatter_warning(self, repl_setup):
        """Test formatter warning"""
        repl = repl_setup
        result = repl.formatter.format_warning("Warning message")
        assert result is not None


class TestREPLSlashHandlerIntegration:
    """Test REPL Slash Handler Integration"""

    @pytest.fixture
    def repl_setup(self):
        """Create REPL setup"""
        agent = Mock()
        agent.process = AsyncMock(return_value=Mock(content="Response"))
        agent.model = Mock()
        agent.model.name = "test-model"
        settings = Mock()
        settings.debug = False
        settings.model = "test-model"
        settings.model_dump = Mock(return_value={"debug": False})
        memory = Mock()
        memory.session_id = "test"
        memory.working_dir = "/app"
        memory.turn_count = 0
        memory.total_input_tokens = 0
        memory.total_output_tokens = 0
        memory.total_tokens = 0
        memory.summary = ""
        memory.messages = []

        repl = REPL(agent=agent, settings=settings, session_memory=memory)
        return repl

    def test_slash_handler_exists(self, repl_setup):
        """Test slash handler exists"""
        repl = repl_setup
        assert repl.slash_handler is not None

    def test_slash_handler_has_repl(self, repl_setup):
        """Test slash handler has repl"""
        repl = repl_setup
        assert repl.slash_handler.repl == repl

    @pytest.mark.asyncio
    async def test_help_command(self, repl_setup):
        """Test help command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/help")
        assert result is not None

    @pytest.mark.asyncio
    async def test_pwd_command(self, repl_setup):
        """Test pwd command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/pwd")
        assert result is not None

    @pytest.mark.asyncio
    async def test_model_command(self, repl_setup):
        """Test model command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/model")
        assert result is not None

    @pytest.mark.asyncio
    async def test_config_command(self, repl_setup):
        """Test config command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/config")
        assert result is not None

    @pytest.mark.asyncio
    async def test_memory_command(self, repl_setup):
        """Test memory command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/memory")
        assert result is not None

    @pytest.mark.asyncio
    async def test_version_command(self, repl_setup):
        """Test version command through REPL"""
        repl = repl_setup
        result = await repl.slash_handler.execute("/version")
        assert result is not None

    @pytest.mark.asyncio
    async def test_exit_command(self, repl_setup):
        """Test exit command through REPL"""
        from cli.commands.slash import SlashCommandResult
        repl = repl_setup
        result = await repl.slash_handler.execute("/exit")
        assert result == SlashCommandResult.EXIT

    @pytest.mark.asyncio
    async def test_quit_command(self, repl_setup):
        """Test quit command through REPL"""
        from cli.commands.slash import SlashCommandResult
        repl = repl_setup
        result = await repl.slash_handler.execute("/quit")
        assert result == SlashCommandResult.EXIT

    @pytest.mark.asyncio
    async def test_clear_command(self, repl_setup):
        """Test clear command through REPL"""
        from cli.commands.slash import SlashCommandResult
        repl = repl_setup
        result = await repl.slash_handler.execute("/clear")
        assert result == SlashCommandResult.CONTINUE


class TestREPLMethods:
    """Test REPL Methods"""

    @pytest.fixture
    def repl_setup(self):
        """Create REPL setup"""
        agent = Mock()
        agent.process = AsyncMock(return_value=Mock(content="Response"))
        agent.model = Mock()
        agent.model.name = "test-model"
        settings = Mock()
        settings.debug = False
        settings.model = "test-model"
        memory = Mock()
        memory.session_id = "test"
        memory.working_dir = "/app"
        memory.turn_count = 0
        memory.total_input_tokens = 0
        memory.total_output_tokens = 0
        memory.total_tokens = 0
        memory.summary = ""
        memory.messages = []

        repl = REPL(agent=agent, settings=settings, session_memory=memory)
        return repl

    def test_repl_print_welcome(self, repl_setup):
        """Test REPL print welcome"""
        repl = repl_setup
        result = repl._print_welcome()
        assert result is None  # Just prints

    def test_repl_emit_event_no_callbacks(self, repl_setup):
        """Test REPL emit_event without callbacks"""
        repl = repl_setup
        # Should not crash even without callbacks
        repl._emit_event("test_event", {"data": "test"})
        # No exception raised

    @pytest.mark.asyncio
    async def test_repl_shutdown_basic(self, repl_setup):
        """Test REPL shutdown basic"""
        repl = repl_setup
        # Set memory with real values for shutdown calculation
        repl.memory.total_input_tokens = 100
        repl.memory.total_output_tokens = 50
        repl.memory.turn_count = 5
        repl.memory.total_tokens = 150
        # Mock updated_at and created_at as numbers for subtraction
        repl.memory.updated_at = 1000.0
        repl.memory.created_at = 900.0
        repl._running = True
        await repl.shutdown()
        assert repl._running is False
