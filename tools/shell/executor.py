"""
Shell 命令执行工具 - execute_shell_command
含超时控制和基础安全过滤
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from core.config import get_settings

from ..base import BaseTool, ExecutionContext

# 高危命令模式（可扩展）
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf?\s+/",          # rm -rf /
    r"\bdd\s+if=.+of=/dev/[sh]d", # dd 覆写磁盘
    r"\bmkfs\b",                   # 格式化文件系统
    r">\s*/dev/[sh]d",             # 重定向到磁盘
    r"\bchmod\s+-R\s+777\s+/",    # 全局 777
    r":\s*\(\)\s*\{.*\};\s*:",     # fork bomb
]

_DANGEROUS_RE = [re.compile(p) for p in _DANGEROUS_PATTERNS]


def _check_dangerous(command: str) -> str | None:
    """返回匹配的危险模式描述，None 表示安全"""
    for pattern in _DANGEROUS_RE:
        if pattern.search(command):
            return pattern.pattern
    return None


class ExecuteShellCommandTool(BaseTool):
    name = "execute_shell_command"
    description = (
        "在 shell 中执行命令并返回输出（stdout + stderr）。"
        "命令在指定工作目录中运行，有超时限制。"
        "高危命令将被拒绝执行。"
    )
    requires_sandbox = True
    timeout = 30

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "cwd": {
                    "type": "string",
                    "description": "执行命令的工作目录（默认为上下文工作目录）",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数（默认 30，最大 300）",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        ctx: ExecutionContext,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> str:
        settings = get_settings()

        # 安全检查
        danger = _check_dangerous(command)
        if danger:
            raise PermissionError(
                f"Command blocked by security policy (matched: {danger}). "
                "This command is potentially dangerous."
            )

        effective_cwd = cwd or ctx.working_dir
        effective_timeout = min(timeout or ctx.timeout or self.timeout, 300)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise TimeoutError(
                    f"Command timed out after {effective_timeout}s: {command[:100]}"
                )

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                output_parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")

            output = "\n".join(output_parts).rstrip()
            rc_line = f"\n[exit code: {proc.returncode}]"

            return (output + rc_line) if output else rc_line

        except PermissionError:
            raise
        except TimeoutError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}") from e
