"""
Grep 文件内容搜索工具 - grep_search
"""
from __future__ import annotations

import os
import re
from typing import Any

import aiofiles

from ..base import BaseTool, ExecutionContext


class GrepSearchTool(BaseTool):
    name = "grep_search"
    description = (
        "在文件或目录中搜索匹配指定模式的内容行（类似 grep）。"
        "输出格式：path:line_number: content。"
        "支持正则表达式搜索。"
    )
    requires_sandbox = False
    timeout = 20

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索字符串或正则表达式",
                },
                "path": {
                    "type": "string",
                    "description": "搜索的文件或目录路径（默认工作目录）",
                },
                "include_pattern": {
                    "type": "string",
                    "description": "只搜索文件名匹配该 glob 的文件，例如 '*.py'",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "是否将 pattern 视为正则表达式（默认 false）",
                    "default": False,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写（默认 true）",
                    "default": True,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "每个匹配前后显示的上下文行数（默认 0，最大 5）",
                    "default": 0,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数（默认 100）",
                    "default": 100,
                },
            },
            "required": ["pattern"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        pattern: str,
        path: str | None = None,
        include_pattern: str | None = None,
        is_regex: bool = False,
        case_sensitive: bool = True,
        context_lines: int = 0,
        max_results: int = 100,
    ) -> str:
        context_lines = min(context_lines, 5)

        # 编译搜索模式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern if is_regex else re.escape(pattern), flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # 确定搜索路径
        root = path if (path and os.path.isabs(path)) else os.path.join(ctx.working_dir, path or "")
        root = os.path.normpath(root)

        results: list[str] = []
        total = 0

        if os.path.isfile(root):
            file_results = await self._search_file(root, regex, context_lines)
            results.extend(file_results)
            total += len(file_results)
        else:
            import fnmatch
            for dirpath, _, filenames in os.walk(root):
                for fname in sorted(filenames):
                    if include_pattern and not fnmatch.fnmatch(fname, include_pattern):
                        continue
                    fpath = os.path.join(dirpath, fname)
                    try:
                        file_results = await self._search_file(fpath, regex, context_lines)
                        results.extend(file_results)
                        total += len(file_results)
                    except (UnicodeDecodeError, PermissionError):
                        continue
                    if total >= max_results:
                        break
                if total >= max_results:
                    break

        if not results:
            return f"No matches found for pattern '{pattern}'"

        output = "\n".join(results[:max_results])
        if total > max_results:
            output += f"\n... (showing first {max_results} of {total}+ matches)"
        return output

    @staticmethod
    async def _search_file(
        filepath: str,
        regex: re.Pattern,
        context_lines: int,
    ) -> list[str]:
        try:
            async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
        except (OSError, PermissionError):
            return []

        lines = content.splitlines()
        results: list[str] = []
        seen_lines: set[int] = set()

        for i, line in enumerate(lines):
            if regex.search(line):
                # 上下文范围
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                for j in range(start, end):
                    if j not in seen_lines:
                        seen_lines.add(j)
                        results.append(f"{filepath}:{j + 1}: {lines[j]}")

        return results
