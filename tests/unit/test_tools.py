"""
工具系统单元测试 - DEV-003
"""
from __future__ import annotations

import os

# 将项目根加入路径
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import register_default_tools
from tools.base import ExecutionContext, ToolRegistry
from tools.file import EditFileTool, GlobSearchTool, GrepSearchTool, ReadFileTool, WriteFileTool
from tools.shell import ExecuteShellCommandTool

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def ctx(tmp_dir):
    return ExecutionContext(
        session_id="test-session",
        working_dir=tmp_dir,
        timeout=10,
    )


@pytest.fixture
def registry():
    """新鲜的注册表（避免全局状态污染）"""
    reg = ToolRegistry()
    return register_default_tools(reg)


# ─── WriteFileTool ────────────────────────────────────────────────────────────

class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_write_new_file(self, ctx, tmp_dir):
        tool = WriteFileTool()
        result = await tool.run(ctx, {"file_path": "hello.txt", "content": "Hello, World!"})
        assert result.success
        assert os.path.exists(os.path.join(tmp_dir, "hello.txt"))
        with open(os.path.join(tmp_dir, "hello.txt")) as f:
            assert f.read() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, ctx, tmp_dir):
        tool = WriteFileTool()
        result = await tool.run(ctx, {"file_path": "nested/deep/file.txt", "content": "test"})
        assert result.success
        assert os.path.exists(os.path.join(tmp_dir, "nested", "deep", "file.txt"))


# ─── ReadFileTool ─────────────────────────────────────────────────────────────

class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_read_full_file(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("line1\nline2\nline3\n")

        tool = ReadFileTool()
        result = await tool.run(ctx, {"file_path": "test.txt"})
        assert result.success
        assert "line1" in result.result
        assert "line3" in result.result

    @pytest.mark.asyncio
    async def test_read_line_range(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "lines.txt")
        with open(path, "w") as f:
            f.write("line1\nline2\nline3\nline4\nline5\n")

        tool = ReadFileTool()
        result = await tool.run(ctx, {"file_path": "lines.txt", "start_line": 2, "end_line": 3})
        assert result.success
        assert "line2" in result.result
        assert "line3" in result.result
        assert "line1" not in result.result
        assert "line4" not in result.result

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, ctx):
        tool = ReadFileTool()
        result = await tool.run(ctx, {"file_path": "nonexistent.txt"})
        assert not result.success
        assert "not found" in result.error.lower()


# ─── EditFileTool ─────────────────────────────────────────────────────────────

class TestEditFileTool:
    @pytest.mark.asyncio
    async def test_simple_replace(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "edit.txt")
        with open(path, "w") as f:
            f.write("Hello World\nHello World\n")

        tool = EditFileTool()
        result = await tool.run(ctx, {
            "file_path": "edit.txt",
            "old_text": "Hello World",
            "new_text": "Hi Earth",
        })
        assert result.success
        assert "2 occurrence" in result.result
        with open(path) as f:
            assert f.read() == "Hi Earth\nHi Earth\n"

    @pytest.mark.asyncio
    async def test_old_text_not_found(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("something")

        tool = EditFileTool()
        result = await tool.run(ctx, {
            "file_path": "test.txt",
            "old_text": "NONEXISTENT",
            "new_text": "replacement",
        })
        assert not result.success
        assert "not found" in result.error.lower()


# ─── GlobSearchTool ───────────────────────────────────────────────────────────

class TestGlobSearchTool:
    @pytest.mark.asyncio
    async def test_glob_py_files(self, ctx, tmp_dir):
        # 创建测试文件
        for name in ["a.py", "b.py", "c.txt"]:
            with open(os.path.join(tmp_dir, name), "w") as f:
                f.write("content")

        tool = GlobSearchTool()
        result = await tool.run(ctx, {"pattern": "*.py"})
        assert result.success
        assert "a.py" in result.result
        assert "b.py" in result.result
        assert "c.txt" not in result.result

    @pytest.mark.asyncio
    async def test_glob_no_match(self, ctx, tmp_dir):
        tool = GlobSearchTool()
        result = await tool.run(ctx, {"pattern": "*.nonexistent"})
        assert result.success
        assert "No files found" in result.result


# ─── GrepSearchTool ───────────────────────────────────────────────────────────

class TestGrepSearchTool:
    @pytest.mark.asyncio
    async def test_simple_search(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "code.py")
        with open(path, "w") as f:
            f.write("def hello():\n    pass\n\ndef world():\n    return 42\n")

        tool = GrepSearchTool()
        result = await tool.run(ctx, {"pattern": "def "})
        assert result.success
        assert "def hello" in result.result
        assert "def world" in result.result

    @pytest.mark.asyncio
    async def test_case_insensitive(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("Hello World\nhello world\nHELLO WORLD\n")

        tool = GrepSearchTool()
        result = await tool.run(ctx, {
            "pattern": "hello",
            "case_sensitive": False,
        })
        assert result.success
        assert result.result.count(":") >= 3  # 3 行都匹配

    @pytest.mark.asyncio
    async def test_no_match(self, ctx, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("some content here")

        tool = GrepSearchTool()
        result = await tool.run(ctx, {"pattern": "ZZZNOMATCH"})
        assert result.success
        assert "No matches" in result.result


# ─── ExecuteShellCommandTool ──────────────────────────────────────────────────

class TestExecuteShellCommandTool:
    @pytest.mark.asyncio
    async def test_simple_echo(self, ctx):
        tool = ExecuteShellCommandTool()
        result = await tool.run(ctx, {"command": "echo 'hello copaw'"})
        assert result.success
        assert "hello copaw" in result.result

    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self, ctx):
        tool = ExecuteShellCommandTool()
        result = await tool.run(ctx, {"command": "rm -rf /"})
        assert not result.success
        assert "blocked" in result.error.lower() or "dangerous" in result.error.lower() or "security" in result.error.lower()

    @pytest.mark.asyncio
    async def test_exit_code_in_output(self, ctx):
        tool = ExecuteShellCommandTool()
        result = await tool.run(ctx, {"command": "exit 0"})
        assert result.success
        assert "exit code: 0" in result.result


# ─── ToolRegistry ─────────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ReadFileTool()
        reg.register(tool)
        assert reg.get("read_file") is tool
        assert "read_file" in reg

    def test_duplicate_register_raises(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(ReadFileTool())

    def test_get_definitions(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "read_file"

    def test_default_tools_registered(self, registry):
        names = registry.get_names()
        expected = ["read_file", "write_file", "edit_file", "glob_search", "grep_search", "execute_shell_command"]
        for name in expected:
            assert name in names, f"Expected tool '{name}' not registered"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = await reg.execute("nonexistent_tool", {})
        assert not result.success
        assert "Unknown tool" in result.error
