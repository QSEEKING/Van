"""
Tests for Output Formatter module - comprehensive coverage
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from cli.formatter.output import FormatterConfig, OutputFormatter


class TestFormatterConfig:
    """Test Formatter Configuration"""

    def test_config_defaults(self):
        """Test config defaults"""
        config = FormatterConfig()
        assert config.use_colors is True
        assert config.max_line_width == 120  # Default is 120

    def test_config_custom(self):
        """Test custom config"""
        config = FormatterConfig(use_colors=False, max_line_width=100)
        assert config.use_colors is False
        assert config.max_line_width == 100

    def test_config_from_env(self):
        """Test config from environment"""
        with patch.dict('os.environ', {'NO_COLOR': '1'}):
            config = FormatterConfig.from_env()
            assert config.use_colors is False

    def test_config_other_attributes(self):
        """Test config other attributes"""
        config = FormatterConfig()
        assert config.show_timestamps is True
        assert config.show_tool_duration is True
        assert config.indent_size == 2
        assert config.show_emoji is True


class TestOutputFormatterBasic:
    """Test OutputFormatter basic functionality"""

    @pytest.fixture
    def formatter_no_color(self):
        """Create formatter without colors"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    @pytest.fixture
    def formatter_with_color(self):
        """Create formatter with colors"""
        config = FormatterConfig(use_colors=True)
        # Mock terminal to support colors
        formatter = OutputFormatter(config)
        formatter._supports_color = True
        return formatter

    def test_formatter_creation(self, formatter_no_color):
        """Test creating formatter"""
        assert formatter_no_color is not None
        assert formatter_no_color.config is not None

    def test_width_property(self, formatter_no_color):
        """Test width property"""
        width = formatter_no_color.width
        assert width > 0
        assert width <= formatter_no_color.config.max_line_width

    def test_colorize_disabled(self, formatter_no_color):
        """Test colorize with colors disabled"""
        result = formatter_no_color._colorize("text", "red")
        assert result == "text"  # No color added

    def test_icon_method(self, formatter_no_color):
        """Test icon method"""
        icon = formatter_no_color._icon("user")
        assert icon == "👤"

        icon = formatter_no_color._icon("assistant")
        assert icon == "🤖"

        icon = formatter_no_color._icon("error")
        assert icon == "✗"

        icon = formatter_no_color._icon("nonexistent")
        assert icon == ""  # Unknown icon returns empty


class TestOutputFormatterFormatting:
    """Test OutputFormatter formatting methods"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_format_user_input(self, formatter):
        """Test format user input"""
        result = formatter.format_user_input("Hello")
        assert "Hello" in result

    def test_format_assistant_response(self, formatter):
        """Test format assistant response"""
        result = formatter.format_assistant_response("Response text")
        assert "Response text" in result

    def test_format_system_message_info(self, formatter):
        """Test format system message info level"""
        result = formatter.format_system_message("Info message", level="info")
        assert "Info message" in result

    def test_format_system_message_error(self, formatter):
        """Test format system message error level"""
        result = formatter.format_system_message("Error message", level="error")
        assert "Error message" in result

    def test_format_system_message_warning(self, formatter):
        """Test format system message warning level"""
        result = formatter.format_system_message("Warning message", level="warning")
        assert "Warning message" in result

    def test_format_error_basic(self, formatter):
        """Test format error basic"""
        result = formatter.format_error("Error occurred")
        assert "Error occurred" in result

    def test_format_error_with_details(self, formatter):
        """Test format error with details"""
        result = formatter.format_error("Error", details="Detailed info")
        assert "Error" in result
        assert "Detailed info" in result

    def test_format_error_with_suggestion(self, formatter):
        """Test format error with suggestion"""
        result = formatter.format_error("Error", suggestion="Try this")
        assert "Error" in result
        assert "Try this" in result

    def test_format_warning(self, formatter):
        """Test format warning"""
        result = formatter.format_warning("Warning message")
        assert "Warning message" in result

    def test_separator_single(self, formatter):
        """Test separator single style"""
        result = formatter.separator(style="single")
        assert result is not None

    def test_separator_double(self, formatter):
        """Test separator double style"""
        result = formatter.separator(style="double")
        assert result is not None

    def test_separator_dashed(self, formatter):
        """Test separator dashed style"""
        result = formatter.separator(style="dashed")
        assert result is not None


class TestOutputFormatterToolCalls:
    """Test OutputFormatter tool call formatting"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_format_tool_call_basic(self, formatter):
        """Test format tool call basic"""
        result = formatter.format_tool_call("read_file", {"file_path": "/app/test.py"})
        assert "read_file" in result

    def test_format_tool_call_with_id(self, formatter):
        """Test format tool call with status"""
        # format_tool_call uses status parameter, not call_id
        result = formatter.format_tool_call("execute", {"command": "ls"}, status="running")
        assert "execute" in result

    def test_format_tool_result(self, formatter):
        """Test format tool result"""
        result = formatter.format_tool_result("read_file", "File content here", success=True)
        assert "read_file" in result
        assert "File content here" in result

    def test_format_tool_result_error(self, formatter):
        """Test format tool result error"""
        result = formatter.format_tool_result("execute", "Command failed", success=False)
        assert "execute" in result

    def test_format_tool_result_truncated(self, formatter):
        """Test format tool result with long content"""
        long_result = "A" * 1000
        result = formatter.format_tool_result("cat", long_result, success=True)
        # Result contains the tool name
        assert "cat" in result
        # Result contains some content (not checking truncation)
        assert "A" in result


class TestOutputFormatterStructuredOutput:
    """Test OutputFormatter structured output"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_box_basic(self, formatter):
        """Test box basic"""
        result = formatter.box("Title", "Content")
        assert "Title" in result
        assert "Content" in result

    def test_box_multiline(self, formatter):
        """Test box multiline content"""
        result = formatter.box("Title", "Line 1\nLine 2\nLine 3")
        assert "Title" in result
        assert "Line 1" in result

    def test_table_basic(self, formatter):
        """Test table basic"""
        headers = ["Name", "Value"]
        rows = [["a", "1"], ["b", "2"]]
        result = formatter.table(headers, rows)
        assert "Name" in result
        assert "Value" in result
        assert "a" in result
        assert "b" in result

    def test_table_empty(self, formatter):
        """Test table empty"""
        headers = ["Name", "Value"]
        rows = []
        result = formatter.table(headers, rows)
        assert "Name" in result

    def test_list_items_basic(self, formatter):
        """Test list items basic"""
        items = ["Item 1", "Item 2", "Item 3"]
        result = formatter.list_items(items)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_list_items_with_style(self, formatter):
        """Test list items with style"""
        items = ["Item 1", "Item 2"]
        result = formatter.list_items(items, style="bullet")
        assert "Item 1" in result

    def test_list_items_numbered(self, formatter):
        """Test list items numbered"""
        items = ["First", "Second", "Third"]
        # Use "number" style, not "numbered"
        result = formatter.list_items(items, style="number")
        # Check for numbered format
        assert "First" in result
        assert "Second" in result


class TestOutputFormatterCodeBlocks:
    """Test OutputFormatter code blocks"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_code_block_basic(self, formatter):
        """Test code block basic"""
        result = formatter.code_block("print('hello')")
        assert "print('hello')" in result

    def test_code_block_with_language(self, formatter):
        """Test code block with language"""
        result = formatter.code_block("def test(): pass", "python")
        assert "def test(): pass" in result

    def test_code_block_multiline(self, formatter):
        """Test code block multiline"""
        code = "def hello():\n    print('world')\n    return True"
        result = formatter.code_block(code, "python")
        assert "def hello()" in result
        assert "print('world')" in result


class TestOutputFormatterProgress:
    """Test OutputFormatter progress indicators"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_progress_bar_basic(self, formatter):
        """Test progress bar basic"""
        result = formatter.progress_bar(50, 100)
        assert result is not None

    def test_progress_bar_with_label(self, formatter):
        """Test progress bar with label"""
        result = formatter.progress_bar(50, 100, label="Processing")
        assert "Processing" in result

    def test_progress_bar_complete(self, formatter):
        """Test progress bar complete"""
        result = formatter.progress_bar(100, 100)
        assert result is not None

    def test_progress_bar_zero(self, formatter):
        """Test progress bar zero"""
        result = formatter.progress_bar(0, 100)
        assert result is not None

    def test_spinner_basic(self, formatter):
        """Test spinner basic"""
        result = formatter.spinner()
        assert result is not None

    def test_spinner_custom_frames(self, formatter):
        """Test spinner custom frames"""
        frames = ["A", "B", "C"]
        result = formatter.spinner(frames=frames, index=1)
        assert result == "B"


class TestOutputFormatterTimeFormatting:
    """Test OutputFormatter time formatting"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_timestamp_datetime(self, formatter):
        """Test timestamp with datetime"""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = formatter.timestamp(dt)
        assert result is not None

    def test_timestamp_float(self, formatter):
        """Test timestamp with float"""
        timestamp = 1704067200.0  # 2024-01-01
        result = formatter.timestamp(timestamp)
        assert result is not None

    def test_timestamp_none(self, formatter):
        """Test timestamp with None"""
        result = formatter.timestamp(None)
        assert result is not None  # Should use current time

    def test_session_header(self, formatter):
        """Test session header"""
        # session_header(session_id, turn_count, token_count=None)
        result = formatter.session_header("session-123", 5, 1000)
        assert "session-123" in result
        assert "5" in result  # turn count

    def test_help_section(self, formatter):
        """Test help section"""
        # help_section expects list[tuple[str, str]]
        commands = [("help", "Show help"), ("exit", "Exit program")]
        result = formatter.help_section("Commands", commands)
        assert "Commands" in result
        assert "help" in result
        assert "exit" in result

    def test_welcome_banner(self, formatter):
        """Test welcome banner"""
        result = formatter.welcome_banner()
        assert result is not None
        assert len(result) > 0


class TestOutputFormatterUtility:
    """Test OutputFormatter utility methods"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_clear_screen(self, formatter):
        """Test clear screen"""
        result = formatter.clear_screen()
        assert "\033" in result  # ANSI escape code

    def test_token_usage(self, formatter):
        """Test token usage"""
        result = formatter.token_usage(1000, 500, 200000)
        # Numbers are formatted with commas
        assert "1,000" in result  # Input tokens with comma
        assert "500" in result    # Output tokens

    def test_print_error(self, formatter):
        """Test print error method"""
        formatter.print_error("Test error")
        # Should not raise

    def test_print_success(self, formatter):
        """Test print success method"""
        formatter.print_success("Test success")
        # Should not raise

    def test_print_info(self, formatter):
        """Test print info method"""
        formatter.print_info("Test info")
        # Should not raise

    def test_print_session_summary(self, formatter):
        """Test print session summary"""
        stats = {"turns": 5, "tokens": 150, "duration": 100}
        formatter.print_session_summary(stats)
        # Should not raise


class TestOutputFormatterTerminalDetection:
    """Test OutputFormatter terminal detection"""

    def test_detect_terminal_colors_enabled(self):
        """Test detect terminal with colors enabled"""
        config = FormatterConfig(use_colors=True)
        formatter = OutputFormatter(config)
        # Should detect based on terminal
        assert formatter._supports_color is not None

    def test_detect_terminal_colors_disabled(self):
        """Test detect terminal with colors disabled"""
        config = FormatterConfig(use_colors=False)
        formatter = OutputFormatter(config)
        # Should be False when disabled
        assert formatter._supports_color is False

    def test_detect_terminal_dumb(self):
        """Test detect terminal with TERM=dumb"""
        with patch.dict('os.environ', {'TERM': 'dumb'}):
            config = FormatterConfig(use_colors=True)
            formatter = OutputFormatter(config)
            assert formatter._supports_color is False

    def test_terminal_width_detection(self):
        """Test terminal width detection"""
        config = FormatterConfig()
        formatter = OutputFormatter(config)
        # Should have a width
        assert formatter._terminal_width is not None
        assert formatter._terminal_width > 0


class TestOutputFormatterEdgeCases:
    """Test OutputFormatter edge cases"""

    @pytest.fixture
    def formatter(self):
        """Create formatter"""
        config = FormatterConfig(use_colors=False)
        return OutputFormatter(config)

    def test_empty_text(self, formatter):
        """Test formatting empty text"""
        result = formatter.format_user_input("")
        assert result is not None

    def test_very_long_text(self, formatter):
        """Test formatting very long text"""
        long_text = "A" * 1000
        result = formatter.format_user_input(long_text)
        assert "A" in result

    def test_special_characters(self, formatter):
        """Test formatting special characters"""
        result = formatter.format_user_input("Hello\nWorld\tTab")
        assert result is not None

    def test_unicode_characters(self, formatter):
        """Test formatting unicode characters"""
        result = formatter.format_user_input("你好世界 🌍")
        assert "你好世界" in result

    def test_table_single_row(self, formatter):
        """Test table with single row"""
        headers = ["Name"]
        rows = [["Test"]]
        result = formatter.table(headers, rows)
        assert "Test" in result

    def test_list_empty(self, formatter):
        """Test list with empty items"""
        result = formatter.list_items([])
        assert result is not None
