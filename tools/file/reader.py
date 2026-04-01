"""
文件读取工具 - read_file
"""
from __future__ import annotations

import os
from typing import Any

import aiofiles

from core.config import get_settings

from ..base import BaseTool, ExecutionContext


class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "读取指定文件的内容。支持通过 start_line/end_line 指定行范围（1-based）。"
        "相对路径基于当前工作目录解析。"
    )
    requires_sandbox = False
    timeout = 10

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（绝对路径或相对路径）",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（1-based，含），可选",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（1-based，含），可选",
                },
            },
            "required": ["file_path"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        settings = get_settings()
        resolved = self._resolve_path(ctx.working_dir, file_path)

        # 安全检查：文件大小
        file_size_mb = os.path.getsize(resolved) / (1024 * 1024)
        if file_size_mb > settings.max_file_size_mb:
            raise ValueError(
                f"File too large: {file_size_mb:.1f}MB > limit {settings.max_file_size_mb}MB"
            )

        async with aiofiles.open(resolved, "r", encoding="utf-8", errors="replace") as f:
            if start_line is None and end_line is None:
                return await f.read()

            lines = await f.readlines()
            s = (start_line - 1) if start_line else 0
            e = end_line if end_line else len(lines)
            selected = lines[s:e]
            # 带行号输出
            result_lines = [
                f"{s + i + 1}: {line}" for i, line in enumerate(selected)
            ]
            return "".join(result_lines)

    @staticmethod
    def _resolve_path(working_dir: str, file_path: str) -> str:
        if os.path.isabs(file_path):
            resolved = file_path
        else:
            resolved = os.path.join(working_dir, file_path)
        resolved = os.path.normpath(resolved)
        if not os.path.exists(resolved):
            raise FileNotFoundError(f"File not found: {resolved}")
        if not os.path.isfile(resolved):
            raise IsADirectoryError(f"Path is a directory, not a file: {resolved}")
        return resolved
