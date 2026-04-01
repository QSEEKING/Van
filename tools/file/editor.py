"""
文件编辑工具 - edit_file (find-and-replace)
"""
from __future__ import annotations

import os
from typing import Any

import aiofiles

from ..base import BaseTool, ExecutionContext


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "在文件中查找 old_text 并替换为 new_text（替换所有匹配项）。"
        "old_text 必须与文件内容完全匹配（包括空白字符）。"
        "文件必须已存在。"
    )
    requires_sandbox = False
    timeout = 15

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要编辑的文件路径",
                },
                "old_text": {
                    "type": "string",
                    "description": "要查找的精确文本（区分大小写）",
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的新文本",
                },
            },
            "required": ["file_path", "old_text", "new_text"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        file_path: str,
        old_text: str,
        new_text: str,
    ) -> str:
        resolved = self._resolve_path(ctx.working_dir, file_path)

        async with aiofiles.open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = await f.read()

        if old_text not in content:
            raise ValueError(
                f"old_text not found in {resolved}. "
                "Make sure the text matches exactly (including whitespace)."
            )

        count = content.count(old_text)
        new_content = content.replace(old_text, new_text)

        async with aiofiles.open(resolved, "w", encoding="utf-8") as f:
            await f.write(new_content)

        return f"Successfully replaced {count} occurrence(s) in {resolved}"

    @staticmethod
    def _resolve_path(working_dir: str, file_path: str) -> str:
        if os.path.isabs(file_path):
            resolved = os.path.normpath(file_path)
        else:
            resolved = os.path.normpath(os.path.join(working_dir, file_path))
        if not os.path.exists(resolved):
            raise FileNotFoundError(f"File not found: {resolved}")
        return resolved
