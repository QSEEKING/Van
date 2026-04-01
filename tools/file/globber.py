"""
Glob 文件搜索工具 - glob_search
"""
from __future__ import annotations

import os
from typing import Any

from ..base import BaseTool, ExecutionContext


class GlobSearchTool(BaseTool):
    name = "glob_search"
    description = (
        "使用 glob 模式递归搜索匹配的文件路径。"
        "支持通配符：* 匹配任意字符，** 匹配任意层目录，? 匹配单字符。"
        "例如：**/*.py 搜索所有 Python 文件。"
    )
    requires_sandbox = False
    timeout = 15

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob 匹配模式，例如 '**/*.py' 或 'src/*.ts'",
                },
                "path": {
                    "type": "string",
                    "description": "搜索根目录（默认为工作目录）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数（默认 200）",
                    "default": 200,
                },
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        pattern: str,
        path: str | None = None,
        max_results: int = 200,
    ) -> str:
        import glob as glob_module

        root = path if path and os.path.isabs(path) else os.path.join(ctx.working_dir, path or "")
        root = os.path.normpath(root)

        full_pattern = os.path.join(root, pattern)
        matches = glob_module.glob(full_pattern, recursive=True)
        matches.sort()

        if len(matches) > max_results:
            matches = matches[:max_results]
            suffix = f"\n... (truncated to {max_results} results)"
        else:
            suffix = ""

        if not matches:
            return f"No files found matching pattern '{pattern}' in {root}"

        result = "\n".join(matches)
        return result + suffix
