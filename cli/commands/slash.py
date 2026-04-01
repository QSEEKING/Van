"""
Slash Commands - 斜杠命令处理器
实现内置命令和自定义命令扩展
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

import structlog

from cli.formatter.output import OutputFormatter

if TYPE_CHECKING:
    from cli.commands.repl import REPL

logger = structlog.get_logger(__name__)


class SlashCommandResult(Enum):
    """命令执行结果"""
    CONTINUE = "continue"  # 继续下一轮输入
    EXIT = "exit"          # 退出 REPL
    ERROR = "error"        # 发生错误


class SlashCommand:
    """斜杠命令定义"""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        aliases: list[str] | None = None,
        usage: str = "",
        examples: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler
        self.aliases = aliases or []
        self.usage = usage
        self.examples = examples or []

    def get_help(self) -> str:
        """获取帮助文本"""
        lines = [f"/{self.name} - {self.description}"]
        if self.usage:
            lines.append(f"  Usage: {self.usage}")
        if self.aliases:
            lines.append(f"  Aliases: {', '.join('/' + a for a in self.aliases)}")
        if self.examples:
            lines.append("  Examples:")
            for ex in self.examples:
                lines.append(f"    {ex}")
        return "\n".join(lines)


class SlashCommandHandler:
    """
    斜杠命令处理器

    支持的命令：
    - /help, /?        - 显示帮助
    - /exit, /quit, /q - 退出程序
    - /clear           - 清屏
    - /cd <path>       - 切换工作目录
    - /pwd             - 显示当前目录
    - /ls [path]       - 列出目录内容
    - /cat <file>      - 显示文件内容
    - /run <cmd>       - 执行 shell 命令
    - /model           - 显示/切换模型
    - /config          - 显示配置
    - /memory          - 显示会话记忆
    - /save <file>     - 保存对话历史
    - /load <file>     - 加载对话历史
    - /reset           - 重置会话
    - /history         - 显示命令历史
    - /debug           - 切换调试模式
    """

    def __init__(self, repl: "REPL") -> None:
        self.repl = repl
        self.formatter = OutputFormatter(repl.settings)
        self._commands: dict[str, SlashCommand] = {}
        self._aliases: dict[str, str] = {}
        self._history: list[str] = []

        # 注册内置命令
        self._register_builtin_commands()

    def _register_builtin_commands(self) -> None:
        """注册内置命令"""

        # 帮助命令
        self.register(
            SlashCommand(
                name="help",
                description="Show available commands",
                handler=self._cmd_help,
                aliases=["?"],
                usage="/help [command]",
                examples=["/help", "/help cd"],
            )
        )

        # 退出命令
        self.register(
            SlashCommand(
                name="exit",
                description="Exit the program",
                handler=self._cmd_exit,
                aliases=["quit", "q"],
            )
        )

        # 清屏
        self.register(
            SlashCommand(
                name="clear",
                description="Clear the screen",
                handler=self._cmd_clear,
                aliases=["cls"],
            )
        )

        # 目录操作
        self.register(
            SlashCommand(
                name="cd",
                description="Change working directory",
                handler=self._cmd_cd,
                usage="/cd <path>",
                examples=["/cd src", "/cd ..", "/cd ~"],
            )
        )

        self.register(
            SlashCommand(
                name="pwd",
                description="Print working directory",
                handler=self._cmd_pwd,
            )
        )

        self.register(
            SlashCommand(
                name="ls",
                description="List directory contents",
                handler=self._cmd_ls,
                usage="/ls [path]",
                examples=["/ls", "/ls src", "/ls -la"],
            )
        )

        # 文件操作
        self.register(
            SlashCommand(
                name="cat",
                description="Display file contents",
                handler=self._cmd_cat,
                usage="/cat <file>",
                examples=["/cat README.md", "/cat src/main.py"],
            )
        )

        # Shell 命令
        self.register(
            SlashCommand(
                name="run",
                description="Execute a shell command",
                handler=self._cmd_run,
                aliases=["!", "shell"],
                usage="/run <command>",
                examples=["/run git status", "/run npm test"],
            )
        )

        # 模型配置
        self.register(
            SlashCommand(
                name="model",
                description="Show or change the current model",
                handler=self._cmd_model,
                usage="/model [model_name]",
                examples=["/model", "/model gpt-4"],
            )
        )

        # 配置
        self.register(
            SlashCommand(
                name="config",
                description="Show current configuration",
                handler=self._cmd_config,
                aliases=["settings"],
            )
        )

        # 记忆
        self.register(
            SlashCommand(
                name="memory",
                description="Show session memory info",
                handler=self._cmd_memory,
            )
        )

        # 保存/加载
        self.register(
            SlashCommand(
                name="save",
                description="Save conversation history to file",
                handler=self._cmd_save,
                usage="/save <file>",
                examples=["/save conversation.json"],
            )
        )

        self.register(
            SlashCommand(
                name="load",
                description="Load conversation history from file",
                handler=self._cmd_load,
                usage="/load <file>",
                examples=["/load conversation.json"],
            )
        )

        # 重置
        self.register(
            SlashCommand(
                name="reset",
                description="Reset the current session",
                handler=self._cmd_reset,
            )
        )

        # 历史
        self.register(
            SlashCommand(
                name="history",
                description="Show command history",
                handler=self._cmd_history,
            )
        )

        # 调试
        self.register(
            SlashCommand(
                name="debug",
                description="Toggle debug mode",
                handler=self._cmd_debug,
            )
        )

        # 版本
        self.register(
            SlashCommand(
                name="version",
                description="Show version information",
                handler=self._cmd_version,
                aliases=["v"],
            )
        )

    def register(self, command: SlashCommand) -> None:
        """注册命令"""
        self._commands[command.name] = command
        for alias in command.aliases:
            self._aliases[alias] = command.name

    async def execute(self, input_str: str) -> SlashCommandResult:
        """执行斜杠命令"""
        # 解析命令
        parts = input_str[1:].strip().split(maxsplit=1)
        if not parts:
            return SlashCommandResult.CONTINUE

        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # 记录历史
        self._history.append(input_str)

        # 查找命令
        if cmd_name in self._commands:
            command = self._commands[cmd_name]
        elif cmd_name in self._aliases:
            command = self._commands[self._aliases[cmd_name]]
        else:
            self.formatter.print_error(f"Unknown command: /{cmd_name}")
            self.formatter.print_info("Type /help for available commands")
            return SlashCommandResult.ERROR

        # 执行命令
        try:
            result = command.handler(args)
            if asyncio.iscoroutine(result):
                result = await result
            return result if isinstance(result, SlashCommandResult) else SlashCommandResult.CONTINUE

        except Exception as e:
            logger.exception(f"Command error: /{cmd_name}")
            self.formatter.print_error(f"Command failed: {e}")
            return SlashCommandResult.ERROR

    # ─── 内置命令处理器 ───────────────────────────────────────────────────────

    def _cmd_help(self, args: str) -> SlashCommandResult:
        """显示帮助"""
        if args:
            # 显示特定命令帮助
            cmd_name = args.strip().lower().lstrip("/")
            if cmd_name in self._commands:
                print(self._commands[cmd_name].get_help())
            elif cmd_name in self._aliases:
                print(self._commands[self._aliases[cmd_name]].get_help())
            else:
                self.formatter.print_error(f"Unknown command: {cmd_name}")
        else:
            # 显示所有命令
            print("\n📚 Available Commands:\n")
            for name, cmd in sorted(self._commands.items()):
                aliases = f" ({', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
                print(f"  /{name:<12} - {cmd.description}{aliases}")
            print("\nType /help <command> for more details.")
        return SlashCommandResult.CONTINUE

    def _cmd_exit(self, args: str) -> SlashCommandResult:
        """退出程序"""
        return SlashCommandResult.EXIT

    def _cmd_clear(self, args: str) -> SlashCommandResult:
        """清屏"""
        # Use ANSI escape sequence instead of os.system for security
        print("\033[2J\033[H", end="", flush=True)
        return SlashCommandResult.CONTINUE

    def _cmd_cd(self, args: str) -> SlashCommandResult:
        """切换目录"""
        if not args:
            # 显示当前目录
            print(f"Current directory: {self.repl.working_dir}")
            return SlashCommandResult.CONTINUE

        path = os.path.expanduser(args.strip())
        if not os.path.isabs(path):
            path = os.path.join(self.repl.working_dir, path)

        try:
            self.repl.working_dir = path
            self.formatter.print_success(f"Changed to: {self.repl.working_dir}")
        except Exception as e:
            self.formatter.print_error(f"Cannot change directory: {e}")
        return SlashCommandResult.CONTINUE

    def _cmd_pwd(self, args: str) -> SlashCommandResult:
        """显示当前目录"""
        print(f"Working directory: {self.repl.working_dir}")
        return SlashCommandResult.CONTINUE

    def _cmd_ls(self, args: str) -> SlashCommandResult:
        """列出目录内容"""
        parts = args.split() if args else []
        path = "."
        show_all = False
        long_format = False

        for part in parts:
            if part == "-a" or part == "-la" or part == "-al":
                show_all = True
                if "l" in part:
                    long_format = True
            elif part == "-l":
                long_format = True
            elif not part.startswith("-"):
                path = part

        full_path = os.path.join(self.repl.working_dir, path)

        try:
            entries = os.listdir(full_path)
            if not show_all:
                entries = [e for e in entries if not e.startswith(".")]

            entries.sort()

            if long_format:
                for entry in entries:
                    entry_path = os.path.join(full_path, entry)
                    stat = os.stat(entry_path)
                    is_dir = os.path.isdir(entry_path)
                    size = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    prefix = "d" if is_dir else "-"
                    print(f"{prefix} {size:>8} {mtime} {entry}")
            else:
                for entry in entries:
                    if os.path.isdir(os.path.join(full_path, entry)):
                        print(f"📁 {entry}/")
                    else:
                        print(f"📄 {entry}")
        except Exception as e:
            self.formatter.print_error(f"Cannot list directory: {e}")
        return SlashCommandResult.CONTINUE

    def _cmd_cat(self, args: str) -> SlashCommandResult:
        """显示文件内容"""
        if not args:
            self.formatter.print_error("Usage: /cat <file>")
            return SlashCommandResult.ERROR

        path = os.path.join(self.repl.working_dir, args.strip())

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            print(content)
        except Exception as e:
            self.formatter.print_error(f"Cannot read file: {e}")
        return SlashCommandResult.CONTINUE

    async def _cmd_run(self, args: str) -> SlashCommandResult:
        """执行 shell 命令"""
        if not args:
            self.formatter.print_error("Usage: /run <command>")
            return SlashCommandResult.ERROR

        # Security check before executing shell command
        from security import get_security_monitor

        monitor = get_security_monitor()
        result = monitor.check_command(args)
        if not result.passed:
            self.formatter.print_error(f"Command blocked: {result.message}")
            return SlashCommandResult.ERROR

        try:
            # Use shlex.split for safer command parsing when possible
            # Note: shell=True is required for complex commands with pipes/ redirections
            # Security is enforced by the SecurityMonitor check above
            result = subprocess.run(
                args,
                shell=True,  # nosec B602 - Security validated by SecurityMonitor
                cwd=self.repl.working_dir,
                capture_output=True,
                text=True,
                timeout=self.repl.settings.command_timeout,
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.returncode != 0:
                self.formatter.print_info(f"Exit code: {result.returncode}")
        except subprocess.TimeoutExpired:
            self.formatter.print_error("Command timed out")
        except Exception as e:
            self.formatter.print_error(f"Command failed: {e}")
        return SlashCommandResult.CONTINUE

    def _cmd_model(self, args: str) -> SlashCommandResult:
        """显示/切换模型"""
        if args:
            new_model = args.strip()
            self.repl.settings.default_model = new_model
            self.formatter.print_success(f"Model changed to: {new_model}")
        else:
            print(f"Current model: {self.repl.settings.default_model}")
            print(f"Provider: {self.repl.settings.default_provider.value}")
        return SlashCommandResult.CONTINUE

    def _cmd_config(self, args: str) -> SlashCommandResult:
        """显示配置"""
        print("\n⚙️  Current Configuration:\n")
        config = self.repl.settings.model_dump()
        for key, value in sorted(config.items()):
            if "key" in key.lower() or "secret" in key.lower():
                value = "***" if value else "(not set)"
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value) if value else "(empty)"
            print(f"  {key:<25} {value}")
        return SlashCommandResult.CONTINUE

    def _cmd_memory(self, args: str) -> SlashCommandResult:
        """显示会话记忆"""
        memory = self.repl.memory
        print("\n🧠 Session Memory:\n")
        print(f"  Session ID:    {memory.session_id}")
        print(f"  Working Dir:   {memory.working_dir}")
        print(f"  Turn Count:    {memory.turn_count}")
        print(f"  Input Tokens:  {memory.total_input_tokens:,}")
        print(f"  Output Tokens: {memory.total_output_tokens:,}")
        print(f"  Total Tokens:  {memory.total_tokens:,}")
        if memory.summary:
            print(f"\n  Summary:\n  {memory.summary[:200]}...")
        return SlashCommandResult.CONTINUE

    def _cmd_save(self, args: str) -> SlashCommandResult:
        """保存对话历史"""
        if not args:
            self.formatter.print_error("Usage: /save <file>")
            return SlashCommandResult.ERROR

        path = os.path.join(self.repl.working_dir, args.strip())

        try:
            data = {
                "session_id": self.repl.memory.session_id,
                "working_dir": self.repl.memory.working_dir,
                "messages": [m.model_dump() for m in self.repl.memory.messages],
                "saved_at": datetime.now().isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.formatter.print_success(f"Conversation saved to: {path}")
        except Exception as e:
            self.formatter.print_error(f"Cannot save: {e}")
        return SlashCommandResult.CONTINUE

    def _cmd_load(self, args: str) -> SlashCommandResult:
        """加载对话历史"""
        if not args:
            self.formatter.print_error("Usage: /load <file>")
            return SlashCommandResult.ERROR

        path = os.path.join(self.repl.working_dir, args.strip())

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 恢复会话
            from core.llm.base import Message
            self.repl.memory.session_id = data.get("session_id", self.repl.memory.session_id)
            self.repl.memory.working_dir = data.get("working_dir", self.repl.memory.working_dir)
            self.repl.memory.messages = [
                Message(**m) for m in data.get("messages", [])
            ]
            self.formatter.print_success(f"Conversation loaded from: {path}")
            self.formatter.print_info(f"Restored {len(self.repl.memory.messages)} messages")
        except Exception as e:
            self.formatter.print_error(f"Cannot load: {e}")
        return SlashCommandResult.CONTINUE

    def _cmd_reset(self, args: str) -> SlashCommandResult:
        """重置会话"""
        from core.memory.session import SessionMemory
        old_dir = self.repl.memory.working_dir
        self.repl.memory = SessionMemory(working_dir=old_dir)
        self.formatter.print_success("Session reset")
        return SlashCommandResult.CONTINUE

    def _cmd_history(self, args: str) -> SlashCommandResult:
        """显示命令历史"""
        if not self._history:
            print("No command history")
            return SlashCommandResult.CONTINUE

        print("\n📜 Command History:\n")
        for i, cmd in enumerate(self._history[-20:], 1):
            print(f"  {i:>3}. {cmd}")
        return SlashCommandResult.CONTINUE

    def _cmd_debug(self, args: str) -> SlashCommandResult:
        """切换调试模式"""
        self.repl.settings.debug = not self.repl.settings.debug
        status = "ON" if self.repl.settings.debug else "OFF"
        self.formatter.print_info(f"Debug mode: {status}")
        return SlashCommandResult.CONTINUE

    def _cmd_version(self, args: str) -> SlashCommandResult:
        """显示版本信息"""
        print(f"\n🐾 CoPaw Code v{self.repl.settings.app_version}\n")
        print(f"  Python:    {sys.version.split()[0]}")
        print(f"  Platform:  {sys.platform}")
        print(f"  Provider:  {self.repl.settings.default_provider.value}")
        print(f"  Model:     {self.repl.settings.default_model}")
        return SlashCommandResult.CONTINUE

    # ─── 扩展方法 ─────────────────────────────────────────────────────────────

    def get_command(self, name: str) -> SlashCommand | None:
        """获取命令"""
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None

    def list_commands(self) -> list[str]:
        """列出所有命令名"""
        return list(self._commands.keys())

    def get_completions(self, prefix: str) -> list[str]:
        """获取命令补全"""
        if not prefix.startswith("/"):
            return []
        prefix = prefix[1:].lower()
        completions = []
        for name in self._commands:
            if name.startswith(prefix):
                completions.append("/" + name)
        for alias in self._aliases:
            if alias.startswith(prefix):
                completions.append("/" + alias)
        return sorted(completions)
