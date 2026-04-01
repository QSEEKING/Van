"""
tools package - 工具系统初始化与注册
DEV-003: 工具系统
"""
from .base import BaseTool, ExecutionContext, ToolRegistry, ToolResult
from .file import EditFileTool, GlobSearchTool, GrepSearchTool, ReadFileTool, WriteFileTool
from .shell import ExecuteShellCommandTool


def register_default_tools(registry: ToolRegistry | None = None) -> ToolRegistry:
    """注册所有默认工具到注册表"""
    if registry is None:
        registry = ToolRegistry.get_instance()

    default_tools: list[BaseTool] = [
        # 文件操作工具
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        GlobSearchTool(),
        GrepSearchTool(),
        # Shell 执行工具
        ExecuteShellCommandTool(),
    ]

    for tool in default_tools:
        if tool.name not in registry:
            registry.register(tool)

    return registry


__all__ = [
    "BaseTool",
    "ExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "GlobSearchTool",
    "GrepSearchTool",
    "ExecuteShellCommandTool",
    "register_default_tools",
]
