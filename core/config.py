"""
CoPaw Code - Core Configuration
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class SandboxLevel(int, Enum):
    NONE = 0       # 直接执行（可信操作）
    TIMEOUT = 1    # 超时控制（低风险）
    GVISOR = 2     # gVisor 隔离（中风险）
    DOCKER = 3     # Docker 隔离（高风险）


class Settings(BaseSettings):
    """全局配置（通过环境变量或 .env 文件覆盖）"""

    # ── 应用基础 ─────────────────────────────────────────────
    app_name: str = "CoPaw Code"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO

    # ── LLM 配置 ─────────────────────────────────────────────
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    default_model: str = "claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 1.0
    request_timeout: int = 120  # 秒

    # ── 数据库 ────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./copaw.db"

    # ── Redis 缓存 ────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = False  # 可选启用

    # ── 安全配置 ──────────────────────────────────────────────
    default_sandbox_level: SandboxLevel = SandboxLevel.TIMEOUT
    command_timeout: int = 30        # shell 命令最长执行秒数
    max_file_size_mb: int = 10       # 读取文件最大 MB
    allowed_shell_commands: list[str] = Field(default_factory=list)
    require_approval_for_write: bool = False

    # ── 记忆系统 ──────────────────────────────────────────────
    session_memory_max_tokens: int = 8000
    long_term_memory_enabled: bool = True
    claude_md_filename: str = "CLAUDE.md"

    # ── API 服务 ──────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/v1"

    # ── Token 预算 ────────────────────────────────────────────
    context_window_limit: int = 200_000  # claude-opus-4-5 上下文
    prompt_budget_ratio: float = 0.4     # 系统提示最多占 40%
    memory_budget_ratio: float = 0.2     # 记忆最多占 20%
    response_budget_ratio: float = 0.4   # 预留响应空间 40%

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}

    def get_prompt_token_budget(self) -> int:
        return int(self.context_window_limit * self.prompt_budget_ratio)

    def get_memory_token_budget(self) -> int:
        return int(self.context_window_limit * self.memory_budget_ratio)


# 全局单例
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings(overrides: dict[str, Any] | None = None) -> Settings:
    """测试用：重置并可选覆盖配置"""
    global _settings
    _settings = Settings(**(overrides or {}))
    return _settings
