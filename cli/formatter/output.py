"""
Output Formatter - CLI输出格式化器
实现美观的终端输出格式
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ColorScheme(Enum):
    """颜色方案"""
    DEFAULT = "default"
    HIGH_CONTRAST = "high_contrast"
    MONOCHROME = "monochrome"


@dataclass
class ANSIColors:
    """ANSI颜色代码"""
    # 标准颜色
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"

    # 样式
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # 重置
    RESET = "\033[0m"

    # 背景
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


@dataclass
class FormatterConfig:
    """格式化配置"""
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    use_colors: bool = True
    show_timestamps: bool = True
    show_tool_duration: bool = True
    max_line_width: int = 120
    indent_size: int = 2
    show_emoji: bool = True

    @classmethod
    def from_env(cls) -> "FormatterConfig":
        """从环境变量创建配置"""
        no_color = os.environ.get("NO_COLOR", "")
        return cls(
            use_colors=not bool(no_color),
            color_scheme=ColorScheme(os.environ.get("COLOR_SCHEME", "default")),
        )


class OutputFormatter:
    """
    CLI输出格式化器
    
    功能：
    - 颜色化输出
    - 代码高亮
    - 错误/警告格式化
    - 工具调用展示
    - 进度指示器
    - 表格格式化
    """

    # 图标映射
    ICONS = {
        "user": "👤",
        "assistant": "🤖",
        "tool": "🔧",
        "success": "✓",
        "error": "✗",
        "warning": "⚠️",
        "info": "ℹ️",
        "loading": "⏳",
        "file": "📄",
        "shell": "⚡",
        "search": "🔍",
        "edit": "✏️",
        "stats": "📊",
        "browser": "🌐",
        "folder": "📁",
    }

    def __init__(self, config: FormatterConfig | None = None):
        self.config = config or FormatterConfig.from_env()
        self._terminal_width: int | None = None
        self._supports_color: bool | None = None

        # 检测终端支持
        self._detect_terminal()

    def _detect_terminal(self) -> None:
        """检测终端特性"""
        # 检测颜色支持
        if not self.config.use_colors:
            self._supports_color = False
        elif os.environ.get("TERM") == "dumb":
            self._supports_color = False
        elif hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            self._supports_color = True
        else:
            self._supports_color = False

        # 检测终端宽度
        try:
            self._terminal_width = shutil.get_terminal_size().columns
        except Exception:
            self._terminal_width = 80

    @property
    def width(self) -> int:
        """终端宽度"""
        return min(self._terminal_width or 80, self.config.max_line_width)

    def _colorize(self, text: str, color: str, style: str = "") -> str:
        """添加颜色"""
        if not self._supports_color:
            return text

        codes = []
        if style:
            codes.append(style)
        if color:
            codes.append(color)

        if codes:
            return "".join(codes) + text + ANSIColors.RESET
        return text

    def _icon(self, name: str) -> str:
        """获取图标"""
        if not self.config.show_emoji:
            return ""
        return self.ICONS.get(name, "")

    # ─── 基础格式化 ────────────────────────────────────────────────────────

    def format_user_input(self, text: str) -> str:
        """格式化用户输入"""
        icon = self._icon("user")
        header = self._colorize(f"{icon} User:", ANSIColors.GREEN, ANSIColors.BOLD)
        return f"{header}\n{text}"

    def format_assistant_response(self, text: str) -> str:
        """格式化助手响应"""
        icon = self._icon("assistant")
        header = self._colorize(f"{icon} CoPaw:", ANSIColors.BLUE, ANSIColors.BOLD)
        return f"{header}\n{text}"

    def format_system_message(self, text: str, level: str = "info") -> str:
        """格式化系统消息"""
        colors = {
            "info": ANSIColors.CYAN,
            "warning": ANSIColors.YELLOW,
            "error": ANSIColors.RED,
            "success": ANSIColors.GREEN,
        }
        icons = {
            "info": self._icon("info"),
            "warning": self._icon("warning"),
            "error": self._icon("error"),
            "success": self._icon("success"),
        }

        color = colors.get(level, ANSIColors.WHITE)
        icon = icons.get(level, "")

        header = self._colorize(f"[SYSTEM] {icon}", color, ANSIColors.BOLD)
        return f"{header} {text}"

    # ─── 工具调用格式化 ──────────────────────────────────────────────────────

    def format_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
        status: str = "running",
        duration_ms: int | None = None,
    ) -> str:
        """格式化工具调用"""
        icon = self._icon("tool")
        header = self._colorize(f"[TOOL] {icon}", ANSIColors.YELLOW, ANSIColors.BOLD)
        name = self._colorize(tool_name, ANSIColors.CYAN)

        # 状态图标
        status_icons = {
            "running": self._colorize(self._icon("loading"), ANSIColors.YELLOW),
            "success": self._colorize(self._icon("success"), ANSIColors.GREEN),
            "error": self._colorize(self._icon("error"), ANSIColors.RED),
        }
        status_icon = status_icons.get(status, "")

        lines = [f"{header} {name} {status_icon}"]

        # 参数显示
        if params:
            for key, value in params.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                lines.append(f"  {key}: {value}")

        # 耗时
        if duration_ms is not None and self.config.show_tool_duration:
            duration_str = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.2f}s"
            lines.append(f"  Duration: {duration_str}")

        return "\n".join(lines)

    def format_tool_result(
        self,
        tool_name: str,
        result: str | dict[str, Any],
        success: bool,
        duration_ms: int | None = None,
    ) -> str:
        """格式化工具结果"""
        icon = self._icon(success and "success" or "error")
        color = success and ANSIColors.GREEN or ANSIColors.RED

        header = self._colorize(f"[TOOL] {icon}", color, ANSIColors.BOLD)
        name = self._colorize(tool_name, ANSIColors.CYAN)

        lines = [f"{header} {name}"]

        # 分隔线
        sep = self._colorize("─" * min(40, self.width - 4), ANSIColors.DIM)
        lines.append(f"  {sep}")

        # 结果内容
        if isinstance(result, dict):
            result_text = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            result_text = str(result)

        # 截断过长结果
        max_result_lines = 20
        result_lines = result_text.split("\n")
        if len(result_lines) > max_result_lines:
            result_lines = result_lines[:max_result_lines]
            result_lines.append("... (truncated)")

        for line in result_lines:
            lines.append(f"  {line}")

        lines.append(f"  {sep}")

        # 耗时
        if duration_ms is not None:
            status = self._colorize("✓ Complete" if success else "✗ Failed", color)
            duration_str = f"{duration_ms}ms" if duration_ms < 1000 else f"{duration_ms / 1000:.2f}s"
            lines.append(f"  {status} | {duration_str}")

        return "\n".join(lines)

    # ─── 错误/警告格式化 ──────────────────────────────────────────────────────

    def format_error(
        self,
        message: str,
        details: str | None = None,
        suggestion: str | None = None,
    ) -> str:
        """格式化错误消息"""
        icon = self._icon("error")
        header = self._colorize(f"[ERROR] {icon}", ANSIColors.RED, ANSIColors.BOLD)

        lines = [f"{header} {message}"]

        # 分隔框
        if details or suggestion:
            sep = self._colorize("━" * min(50, self.width - 4), ANSIColors.RED)
            lines.append(sep)

            if details:
                lines.append(f"Details: {details}")

            if suggestion:
                suggestion_text = self._colorize(suggestion, ANSIColors.CYAN)
                lines.append(f"Suggestion: {suggestion_text}")

            lines.append(sep)

        return "\n".join(lines)

    def format_warning(
        self,
        message: str,
        details: str | None = None,
    ) -> str:
        """格式化警告消息"""
        icon = self._icon("warning")
        header = self._colorize(f"[WARNING] {icon}", ANSIColors.YELLOW, ANSIColors.BOLD)

        lines = [f"{header} {message}"]

        if details:
            sep = self._colorize("─" * min(40, self.width - 4), ANSIColors.DIM)
            lines.append(sep)
            lines.append(details)
            lines.append(sep)

        return "\n".join(lines)

    # ─── 分隔线和框 ──────────────────────────────────────────────────────────

    def separator(self, style: str = "single") -> str:
        """创建分隔线"""
        chars = {
            "single": "─",
            "double": "═",
            "bold": "━",
            "dashed": "╌",
            "dotted": "┄",
        }
        char = chars.get(style, "─")
        return self._colorize(char * self.width, ANSIColors.DIM)

    def box(
        self,
        content: str,
        title: str | None = None,
        style: str = "single",
    ) -> str:
        """创建框"""
        # 框字符
        box_chars = {
            "single": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"},
            "double": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"},
        }

        chars = box_chars.get(style, box_chars["single"])

        # 内容宽度
        content_lines = content.split("\n")
        max_content_width = max(len(line) for line in content_lines)
        box_width = min(max_content_width + 4, self.width)

        lines = []

        # 顶部
        if title:
            title_line = f" {title} "
            top = chars["tl"] + chars["h"] * (box_width - len(title_line) - 2) + title_line + chars["h"] + chars["tr"]
        else:
            top = chars["tl"] + chars["h"] * (box_width - 2) + chars["tr"]
        lines.append(self._colorize(top, ANSIColors.BLUE))

        # 内容
        for line in content_lines:
            padded = line.ljust(box_width - 4)
            lines.append(self._colorize(f"{chars['v']} ", ANSIColors.BLUE) + padded + self._colorize(f" {chars['v']}", ANSIColors.BLUE))

        # 底部
        bottom = chars["bl"] + chars["h"] * (box_width - 2) + chars["br"]
        lines.append(self._colorize(bottom, ANSIColors.BLUE))

        return "\n".join(lines)

    # ─── 表格格式化 ────────────────────────────────────────────────────────────

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        title: str | None = None,
    ) -> str:
        """创建表格"""
        # 计算列宽
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(header)
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(row[i]))
            col_widths.append(min(max_width, (self.width - len(headers) - 1) // len(headers)))

        lines = []

        # 标题
        if title:
            lines.append(self._colorize(title, ANSIColors.BOLD, ANSIColors.UNDERLINE))

        # 头部
        header_line = "│"
        for i, header in enumerate(headers):
            header_line += " " + self._colorize(header[:col_widths[i]].ljust(col_widths[i]), ANSIColors.BOLD, ANSIColors.CYAN) + " │"
        lines.append(self._colorize("┌" + "─" * (sum(col_widths) + len(headers) * 3 + 1) + "┐", ANSIColors.BLUE))
        lines.append(header_line)
        lines.append(self._colorize("├" + "─" * (sum(col_widths) + len(headers) * 3 + 1) + "┤", ANSIColors.BLUE))

        # 行
        for row in rows:
            row_line = "│"
            for i in range(len(headers)):
                cell = row[i] if i < len(row) else ""
                row_line += " " + cell[:col_widths[i]].ljust(col_widths[i]) + " │"
            lines.append(row_line)

        lines.append(self._colorize("└" + "─" * (sum(col_widths) + len(headers) * 3 + 1) + "┘", ANSIColors.BLUE))

        return "\n".join(lines)

    # ─── 进度指示 ──────────────────────────────────────────────────────────────

    def progress_bar(
        self,
        current: int,
        total: int,
        label: str = "",
        width: int = 40,
    ) -> str:
        """创建进度条"""
        if total == 0:
            percent = 100
        else:
            percent = min(100, int(current / total * 100))

        filled = int(width * percent / 100)
        empty = width - filled

        bar = self._colorize("█" * filled, ANSIColors.GREEN) + self._colorize("░" * empty, ANSIColors.DIM)
        percent_text = self._colorize(f"{percent}%", ANSIColors.BOLD)

        line = f"[{bar}] {percent_text}"
        if label:
            line += f" {label}"

        return line

    def spinner(self, frames: list[str] | None = None, index: int = 0) -> str:
        """创建spinner动画"""
        if frames is None:
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        frame = frames[index % len(frames)]
        return self._colorize(frame, ANSIColors.CYAN)

    # ─── 代码格式化 ────────────────────────────────────────────────────────────

    def code_block(
        self,
        code: str,
        language: str = "",
        line_numbers: bool = True,
    ) -> str:
        """格式化代码块"""
        lines = []

        # 语言标签
        if language:
            lang_tag = self._colorize(f"```{language}", ANSIColors.DIM)
            lines.append(lang_tag)

        # 代码行
        code_lines = code.split("\n")
        for i, line in enumerate(code_lines, 1):
            if line_numbers:
                num = self._colorize(f"{i:4d}", ANSIColors.DIM)
                lines.append(f"{num}  {line}")
            else:
                lines.append(line)

        if language:
            lines.append(self._colorize("```", ANSIColors.DIM))

        return "\n".join(lines)

    # ─── 列表格式化 ────────────────────────────────────────────────────────────

    def list_items(
        self,
        items: list[str],
        style: str = "bullet",
        indent: int = 0,
    ) -> str:
        """格式化列表"""
        markers = {
            "bullet": "•",
            "number": "{i}.",
            "check": "[{check}]",
            "dash": "-",
        }

        lines = []
        prefix = " " * indent

        for i, item in enumerate(items):
            marker = markers.get(style, "•")

            if style == "number":
                marker = f"{i + 1}."
            elif style == "check":
                # 检查是否已完成（假设 item 以 ✓ 开头表示完成）
                check = "✓" if item.startswith("✓") or item.startswith("[x]") else " "
                marker = f"[{check}]"

            lines.append(f"{prefix}{marker} {item}")

        return "\n".join(lines)

    # ─── 时间戳 ────────────────────────────────────────────────────────────────

    def timestamp(self, time: datetime | float | None = None) -> str:
        """格式化时间戳"""
        if time is None:
            dt = datetime.now()
        elif isinstance(time, float):
            dt = datetime.fromtimestamp(time)
        else:
            dt = time

        if self.config.show_timestamps:
            return self._colorize(dt.strftime("%H:%M:%S"), ANSIColors.DIM)
        return ""

    # ─── 会话信息 ──────────────────────────────────────────────────────────────

    def session_header(
        self,
        session_id: str,
        turn_count: int,
        token_count: int | None = None,
    ) -> str:
        """格式化会话头部"""
        sep = self.separator("double")

        info = f"Session #{session_id} | Turns: {turn_count}"
        if token_count is not None:
            info += f" | Tokens: {token_count:,}"

        timestamp = self.timestamp()
        if timestamp:
            info += f" | {timestamp}"

        return f"{sep}\n{info}\n{sep}"

    # ─── 帮助信息 ──────────────────────────────────────────────────────────────

    def help_section(
        self,
        title: str,
        commands: list[tuple[str, str]],
    ) -> str:
        """格式化帮助信息"""
        lines = []

        title_line = self._colorize(f"[{title}]", ANSIColors.BOLD, ANSIColors.CYAN)
        lines.append(title_line)

        for cmd, desc in commands:
            cmd_text = self._colorize(f"  {cmd}", ANSIColors.GREEN)
            lines.append(f"{cmd_text} - {desc}")

        return "\n".join(lines)

    # ─── 欢迎界面 ──────────────────────────────────────────────────────────────

    def welcome_banner(self) -> str:
        """创建欢迎横幅"""
        logo = """
    █████╗  ██████╗ ██████╗███████╗███████╗ ██████╗
   ██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██╔═══██╗
   ███████║██║     ██║     █████╗  ███████╗██║   ██║
   ██╔══██║██║     ██║     ██╔══╝  ╚════██║██║   ██║
   ██║  ██║╚██████╗╚██████╗███████╗███████║╚██████╔╝
   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝╚══════╝╚══════╝ ╚═════╝
"""

        lines = []

        # 顶部边框
        sep = self.separator("double")
        lines.append(sep)

        # Logo
        lines.append(self._colorize(logo, ANSIColors.BLUE, ANSIColors.BOLD))

        # 副标题
        subtitle = self._colorize("⚡ AI Coding Assistant ⚡", ANSIColors.CYAN)
        lines.append(f"          {subtitle}")

        lines.append(sep)

        return "\n".join(lines)

    # ─── 清屏 ───────────────────────────────────────────────────────────────────

    def clear_screen(self) -> str:
        """清屏ANSI序列"""
        return "\033[2J\033[H"

    # ─── 打印方法 ──────────────────────────────────────────────────────────────

    def print_error(self, message: str) -> None:
        """打印错误消息"""
        formatted = self.format_error(message)
        print(formatted)

    def print_success(self, message: str) -> None:
        """打印成功消息"""
        formatted = self.format_system_message(message, level="success")
        print(formatted)

    def print_info(self, message: str) -> None:
        """打印信息消息"""
        formatted = self.format_system_message(message, level="info")
        print(formatted)

    def print_session_summary(self, stats: dict) -> None:
        """打印会话摘要"""
        print("\n📊 Session Summary:")
        print(f"  Turns: {stats.get('turns', 0)}")
        print(f"  Tokens: {stats.get('tokens', 0)}")
        print(f"  Duration: {stats.get('duration', 0)}s")

    # ─── Token统计 ──────────────────────────────────────────────────────────────

    def token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        total_limit: int = 200000,
    ) -> str:
        """格式化Token使用统计"""
        total = input_tokens + output_tokens
        percent = min(100, int(total / total_limit * 100))

        # 进度条
        bar = self.progress_bar(total, total_limit, "", 20)

        # 统计文本
        stats = f"Input: {input_tokens:,} | Output: {output_tokens:,} | Total: {total:,} / {total_limit:,} ({percent}%)"

        return f"{bar}\n{stats}"
