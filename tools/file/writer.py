"""
文件写入工具 - write_file
"""
from __future__ import annotations

import os
from typing import Any

import aiofiles

from ..base import BaseTool, ExecutionContext


class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "创建或覆盖写入文件内容。会自动创建不存在的父目录。"
        "写入前请先用 read_file 检查文件是否存在，避免意外覆盖。"
    )
    requires_sandbox = False
    timeout = 10

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要写入的文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "写入的文件内容",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        file_path: str,
        content: str,
    ) -> str:
        resolved = self._resolve_path(ctx.working_dir, file_path)
        parent = os.path.dirname(resolved)
        if parent:
            os.makedirs(parent, exist_ok=True)

        async with aiofiles.open(resolved, "w", encoding="utf-8") as f:
            await f.write(content)

        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"Successfully wrote {len(content)} bytes ({lines} lines) to {resolved}"

    @staticmethod
    def _resolve_path(working_dir: str, file_path: str) -> str:
        if os.path.isabs(file_path):
            return os.path.normpath(file_path)
        return os.path.normpath(os.path.join(working_dir, file_path))
