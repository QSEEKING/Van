"""
REPL - 交互式命令循环
实现 Read-Eval-Print Loop 核心逻辑
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

import structlog
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from cli.commands.slash import SlashCommandHandler, SlashCommandResult
from cli.formatter.output import OutputFormatter
from core.agent.main_agent import AgentEvent, MainAgent
from core.config import Settings
from core.memory.session import SessionMemory

logger = structlog.get_logger(__name__)


class REPLConfig:
    """REPL 配置"""

    # 提示符
    PROMPT_USER = "❯ "
    PROMPT_CONTINUE = "... "
    PROMPT_TOOL = "🔧 "

    # 历史文件
    HISTORY_FILE = os.path.expanduser("~/.copaw_history")

    # 样式
    STYLE = Style.from_dict({
        "prompt": "bold cyan",
        "user": "green",
        "assistant": "blue",
        "tool": "yellow",
        "error": "red bold",
        "info": "dim",
    })


class REPL:
    """
    交互式命令循环 (REPL)

    功能：
    - 处理用户输入
    - 区分普通消息和斜杠命令
    - 流式输出助手响应
    - 工具调用状态显示
    - 会话历史管理
    """

    def __init__(
        self,
        agent: MainAgent,
        settings: Settings,
        session_memory: SessionMemory | None = None,
    ) -> None:
        self.agent = agent
        self.settings = settings
        self.memory = session_memory or SessionMemory()

        # 组件
        self.slash_handler = SlashCommandHandler(self)
        self.formatter = OutputFormatter(settings)

        # 状态
        self._running = False
        self._multiline_buffer: list[str] = []
        self._current_task: asyncio.Task | None = None

        # 提示会话
        self._prompt_session: PromptSession | None = None

        # 回调钩子
        self._on_event: Callable[[str, Any], None] | None = None

    @property
    def is_running(self) -> bool:
        """REPL 是否正在运行"""
        return self._running

    @property
    def working_dir(self) -> str:
        """当前工作目录"""
        return self.memory.working_dir

    @working_dir.setter
    def working_dir(self, path: str) -> None:
        """设置工作目录"""
        if os.path.isdir(path):
            self.memory.working_dir = os.path.abspath(path)
            os.chdir(self.memory.working_dir)
            logger.info(f"Working directory changed to: {self.memory.working_dir}")
        else:
            raise ValueError(f"Directory not found: {path}")

    def _create_prompt_session(self) -> PromptSession:
        """创建增强的提示会话"""
        # 键盘绑定
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            """Ctrl+C: 取消当前输入或操作"""
            if self._multiline_buffer:
                self._multiline_buffer = []
                event.app.current_buffer.text = ""
                print("\nCancelled")
            elif self._current_task:
                self._current_task.cancel()
            else:
                raise KeyboardInterrupt

        @kb.add("c-d")
        def _(event):
            """Ctrl+D: 退出"""
            if not event.app.current_buffer.text:
                raise EOFError

        @kb.add("escape", "enter")
        def _(event):
            """Esc+Enter: 多行输入"""
            event.app.current_buffer.insert_text("\n")

        # 确保历史目录存在
        history_dir = os.path.dirname(REPLConfig.HISTORY_FILE)
        if history_dir:
            os.makedirs(history_dir, exist_ok=True)

        return PromptSession(
            history=FileHistory(REPLConfig.HISTORY_FILE),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
            style=REPLConfig.STYLE,
            mouse_support=True,
            enable_system_prompt=True,
        )

    async def start(self) -> None:
        """启动 REPL 主循环"""
        self._running = True
        self._prompt_session = self._create_prompt_session()

        # 欢迎消息
        self._print_welcome()

        while self._running:
            try:
                # 获取用户输入
                user_input = await self._read_input()

                if not user_input.strip():
                    continue

                # 处理输入
                await self._process_input(user_input)

            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                await self.shutdown()
                break
            except Exception as e:
                logger.exception("REPL error")
                self.formatter.print_error(f"Error: {e}")
                continue

    async def _read_input(self) -> str:
        """读取用户输入"""
        # 确定提示符
        if self._multiline_buffer:
            prompt = REPLConfig.PROMPT_CONTINUE
        else:
            prompt = REPLConfig.PROMPT_USER

        # 获取输入
        try:
            text = await self._prompt_session.prompt_async(
                prompt,
                multiline=False,
            )
        except Exception as e:
            logger.debug(f"Prompt error: {e}")
            return ""

        # 处理多行
        if text.endswith("\\"):
            self._multiline_buffer.append(text[:-1])
            return ""

        if self._multiline_buffer:
            self._multiline_buffer.append(text)
            text = "\n".join(self._multiline_buffer)
            self._multiline_buffer = []

        return text

    async def _process_input(self, user_input: str) -> None:
        """处理用户输入"""
        # 检查是否是斜杠命令
        if user_input.startswith("/"):
            await self._handle_slash_command(user_input)
            return

        # 检查是否是特殊命令
        if user_input.lower() in ("exit", "quit", "q"):
            await self.shutdown()
            return

        # 发送给 Agent
        await self._send_to_agent(user_input)

    async def _handle_slash_command(self, command: str) -> None:
        """处理斜杠命令"""
        result = await self.slash_handler.execute(command)

        if result == SlashCommandResult.EXIT:
            await self.shutdown()
        elif result == SlashCommandResult.ERROR:
            # 错误已由 handler 打印
            pass
        # CONTINUE - 继续下一轮

    async def _send_to_agent(self, user_input: str) -> None:
        """发送消息到 Agent 并处理响应"""
        # 记录用户消息
        self.memory.add_user_message(user_input)

        # 发送事件
        self._emit_event("user_message", user_input)

        try:
            # 流式处理 Agent 响应
            self._current_task = asyncio.create_task(
                self._run_agent_stream(user_input)
            )
            await self._current_task

        except asyncio.CancelledError:
            self.formatter.print_info("\nCancelled by user")
        except Exception as e:
            logger.exception("Agent error")
            self.formatter.print_error(f"Agent error: {e}")
        finally:
            self._current_task = None

    async def _run_agent_stream(self, user_input: str) -> None:
        """运行 Agent 流式处理"""
        async for event in self.agent.stream(user_input, self.memory):
            await self._handle_agent_event(event)

    async def _handle_agent_event(self, event: AgentEvent) -> None:
        """处理 Agent 事件"""
        if event.event_type == "text":
            # 文本内容
            self.formatter.print_assistant(str(event.data), stream=True)
            self._emit_event("assistant_text", event.data)

        elif event.event_type == "text_done":
            # 文本完成
            self.formatter.print_assistant(str(event.data), stream=False)
            self.memory.add_assistant_message(str(event.data))
            self._emit_event("assistant_done", event.data)

        elif event.event_type == "tool_start":
            # 工具开始
            tool_info = event.data  # {"name": str, "input": dict}
            self.formatter.print_tool_start(
                tool_info.get("name", "unknown"),
                tool_info.get("input", {})
            )
            self._emit_event("tool_start", event.data)

        elif event.event_type == "tool_end":
            # 工具结束
            result = event.data  # ToolResult
            self.formatter.print_tool_result(result)
            self._emit_event("tool_end", event.data)

        elif event.event_type == "done":
            # 对话结束
            self._emit_event("done", None)

        elif event.event_type == "error":
            # 错误
            self.formatter.print_error(str(event.data))
            self._emit_event("error", event.data)

    def _print_welcome(self) -> None:
        """打印欢迎消息"""
        welcome = f"""
╔══════════════════════════════════════════════════════════════╗
║  🐾 CoPaw Code v{self.settings.app_version}                            ║
║  AI-Powered Coding Assistant                                 ║
╚══════════════════════════════════════════════════════════════╝

Working directory: {self.working_dir}
Model: {self.settings.default_model}

Type your request or use /help for available commands.
"""
        print(welcome)

    def _emit_event(self, event_type: str, data: Any) -> None:
        """发出事件"""
        if self._on_event:
            try:
                self._on_event(event_type, data)
            except Exception:
                pass

    async def shutdown(self) -> None:
        """关闭 REPL"""
        self._running = False

        # 保存会话
        self.formatter.print_info("\nSaving session...")

        # 显示统计
        self._print_summary()

        self.formatter.print_info("Goodbye! 👋")

    def _print_summary(self) -> None:
        """打印会话摘要"""
        stats = {
            "turns": self.memory.turn_count,
            "tokens": self.memory.total_tokens,
            "duration": int(self.memory.updated_at - self.memory.created_at),
        }
        self.formatter.print_session_summary(stats)

    # ─── 公共方法 ─────────────────────────────────────────────────────────

    def on_event(self, callback: Callable[[str, Any], None]) -> None:
        """注册事件回调"""
        self._on_event = callback

    def stop(self) -> None:
        """停止 REPL"""
        self._running = False
        if self._current_task:
            self._current_task.cancel()

    def print(self, message: str, style: str | None = None) -> None:
        """打印消息"""
        if style == "error":
            self.formatter.print_error(message)
        elif style == "info":
            self.formatter.print_info(message)
        elif style == "success":
            self.formatter.print_success(message)
        else:
            print(message)


# ─── 异步运行入口 ─────────────────────────────────────────────────────────

async def run_repl(agent: MainAgent, settings: Settings) -> None:
    """运行 REPL 的便捷函数"""
    repl = REPL(agent, settings)
    await repl.start()


def run_repl_sync(agent: MainAgent, settings: Settings) -> None:
    """同步运行 REPL"""
    asyncio.run(run_repl(agent, settings))
