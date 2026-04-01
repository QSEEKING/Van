"""
Performance benchmarks for CoPaw Code.

Run with: pytest tests/benchmarks/ -v --benchmark-only
Or: python -m pytest tests/benchmarks/ -v
"""

import statistics
import timeit
from typing import Callable


class TestPerformance:
    """Performance benchmarks for core functionality."""

    def test_tool_registration_performance(self, benchmark: Callable) -> None:
        """Benchmark tool registration."""
        from tools import ToolRegistry, register_default_tools

        def register_tools() -> int:
            registry = ToolRegistry.get_instance()
            registry.clear()
            register_default_tools()
            return len(registry.list_tools())

        result = benchmark(register_tools)
        assert result > 0

    def test_security_check_performance(self, benchmark: Callable) -> None:
        """Benchmark security checks."""
        from security import get_security_monitor

        monitor = get_security_monitor()

        def check_operation() -> bool:
            result = monitor.check_operation("read", "/app/test.py")
            return result.passed

        result = benchmark(check_operation)
        assert isinstance(result, bool)

    def test_permission_check_performance(self, benchmark: Callable) -> None:
        """Benchmark permission checks."""
        from security import Permission, PermissionManager, Role

        manager = PermissionManager()
        manager.grant(Role.USER, Permission.READ | Permission.WRITE)

        def check_permission() -> bool:
            return manager.check(Role.USER, Permission.READ)

        result = benchmark(check_permission)
        assert result is True

    def test_formatter_performance(self, benchmark: Callable) -> None:
        """Benchmark output formatting."""
        from cli.formatter.output import OutputFormatter

        formatter = OutputFormatter()

        def format_output() -> str:
            return formatter.code_block(
                "print('Hello, World!')",
                language="python",
            )

        result = benchmark(format_output)
        assert "print" in result

    def test_config_loading_performance(self, benchmark: Callable) -> None:
        """Benchmark configuration loading."""
        from core.config import get_config

        def load_config():
            return get_config()

        result = benchmark(load_config)
        assert result is not None


class TestMemoryUsage:
    """Memory usage benchmarks."""

    def test_tool_registry_memory(self) -> None:
        """Test tool registry memory footprint."""
        from tools import ToolRegistry, register_default_tools

        registry = ToolRegistry.get_instance()
        initial_count = len(registry.list_tools())

        # Register tools
        register_default_tools()
        final_count = len(registry.list_tools())

        assert final_count >= initial_count


class TestThroughput:
    """Throughput benchmarks."""

    def test_file_read_throughput(self, tmp_path, benchmark: Callable) -> None:
        """Test file reading throughput."""
        # Create test file
        test_file = tmp_path / "test.py"
        content = "# Test file\n" * 1000
        test_file.write_text(content)

        def read_file() -> str:
            return test_file.read_text()

        result = benchmark(read_file)
        assert len(result) > 0

    def test_pattern_search_throughput(self, benchmark: Callable) -> None:
        """Test pattern search throughput."""
        import re

        content = "def test_function():\n    pass\n" * 1000
        pattern = re.compile(r"def \w+\(")

        def search() -> int:
            return len(pattern.findall(content))

        result = benchmark(search)
        assert result == 1000


if __name__ == "__main__":
    # Run simple benchmarks without pytest-benchmark
    print("Running simple benchmarks...")

    # Security check benchmark
    times = timeit.repeat(
        'from security import get_security_monitor; m = get_security_monitor(); m.check_operation("read", "/app/test.py")',
        number=1000,
        repeat=5,
    )
    print(f"Security check: {statistics.mean(times)*1000:.3f}ms (±{statistics.stdev(times)*1000:.3f}ms)")

    # Formatter benchmark
    times = timeit.repeat(
        'from cli.formatter.output import OutputFormatter; f = OutputFormatter(); f.code_block("print(1)", "python")',
        number=1000,
        repeat=5,
    )
    print(f"Formatter: {statistics.mean(times)*1000:.3f}ms (±{statistics.stdev(times)*1000:.3f}ms)")

    print("\nBenchmarks complete!")
