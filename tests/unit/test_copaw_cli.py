"""
Tests for CLI entry point.

Tests the click-based CLI commands for CoPaw Code.
"""

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestCLI:
    """Tests for main CLI group."""

    def test_cli_version(self, runner):
        """CLI should show version."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_help(self, runner):
        """CLI should show help."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CoPaw Code" in result.output


class TestVersionCommand:
    """Tests for version command."""

    def test_version_shows_version(self, runner):
        """Version command should show version."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestConfigCommand:
    """Tests for config command."""

    def test_config_shows_config(self, runner):
        """Config command should show configuration."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "Configuration" in result.output


class TestShellCommand:
    """Tests for shell command."""

    def test_shell_starts(self, runner):
        """Shell command should start."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["shell"])
        assert result.exit_code == 0
        assert "CoPaw Code" in result.output


class TestRunCommand:
    """Tests for run command."""

    def test_run_with_prompt(self, runner):
        """Run command should process prompt."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["run", "test prompt"])
        assert result.exit_code == 0
        assert "Processing" in result.output


class TestAPICommand:
    """Tests for API command."""

    def test_api_help(self, runner):
        """API command should show help."""
        from copaw.entrypoint import cli

        result = runner.invoke(cli, ["api", "--help"])
        assert result.exit_code == 0
        assert "API server" in result.output
