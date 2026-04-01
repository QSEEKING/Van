"""
提示组合构建器 - DEV-002 提示管理系统

功能：
- 动态组装提示片段
- 优先级排序
- Token预算管理集成
- 消息格式构建
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

from .loader import TemplateLoader, TemplateNotFoundError
from .token_budget import BudgetConfig, TokenBudgetManager

logger = structlog.get_logger(__name__)


class Priority(IntEnum):
    """提示部分优先级（数值越大优先级越高）"""
    SYSTEM = 100      # 系统提示最高优先级
    AGENT = 80        # 代理提示
    TOOLS = 60        # 工具提示
    MEMORY = 40       # 记忆提示
    USER = 20         # 用户消息
    HISTORY = 15      # 对话历史
    RESERVED = 10     # 预留响应空间


@dataclass
class PromptSection:
    """提示片段"""
    name: str
    content: str
    priority: Priority
    token_count: int = 0
    required: bool = True  # 是否必需（不可裁剪）
    metadata: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: PromptSection) -> bool:
        """排序：优先级高的排在前面"""
        return self.priority > other.priority


@dataclass
class PromptContext:
    """提示构建上下文"""
    session_id: str
    agent_type: str = "main"
    user_message: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    project_context: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "user_message": self.user_message,
            "conversation_history": self.conversation_history,
            "available_tools": self.available_tools,
            "memories": self.memories,
            "project_context": self.project_context,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "variables": self.variables,
        }


@dataclass
class BuildResult:
    """构建结果"""
    messages: list[dict[str, str]]
    total_tokens: int
    sections: list[dict[str, Any]]
    budget_used: dict[str, int]
    truncated: bool = False
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "messages": self.messages,
            "total_tokens": self.total_tokens,
            "sections": self.sections,
            "budget_used": self.budget_used,
            "truncated": self.truncated,
            "cache_hit": self.cache_hit,
        }


class PromptBuilder:
    """提示组合构建器
    
    主要功能：
    1. 组装系统提示、代理提示、工具提示、记忆提示
    2. 处理优先级和Token预算
    3. 构建符合LLM API格式的消息列表
    """

    # 代理类型到模板的映射
    AGENT_TEMPLATES = {
        "main": "agents/main",
        "explore": "agents/explore",
        "plan": "agents/plan",
        "verify": "agents/verify",
    }

    def __init__(
        self,
        loader: TemplateLoader,
        budget_config: BudgetConfig | None = None
    ):
        self.loader = loader
        self.budget_manager = TokenBudgetManager(budget_config)
        self._build_cache: dict[str, BuildResult] = {}

    async def build(self, ctx: PromptContext) -> BuildResult:
        """
        构建完整的消息列表
        
        Args:
            ctx: 提示构建上下文
            
        Returns:
            BuildResult 包含消息列表和元信息
        """
        sections: list[PromptSection] = []

        # 1. 加载系统提示
        system_content = await self._load_system_prompt(ctx)
        sections.append(PromptSection(
            name="system",
            content=system_content,
            priority=Priority.SYSTEM,
            required=True,
            metadata={"template": "system/base"}
        ))

        # 2. 加载代理提示
        agent_content = await self._load_agent_prompt(ctx)
        if agent_content:
            sections.append(PromptSection(
                name="agent",
                content=agent_content,
                priority=Priority.AGENT,
                required=True,
                metadata={"template": self.AGENT_TEMPLATES.get(ctx.agent_type)}
            ))

        # 3. 加载工具提示
        tools_content = await self._build_tools_prompt(ctx)
        if tools_content:
            sections.append(PromptSection(
                name="tools",
                content=tools_content,
                priority=Priority.TOOLS,
                required=False,
                metadata={"tool_count": len(ctx.available_tools)}
            ))

        # 4. 加载记忆提示
        memory_content = await self._build_memory_prompt(ctx)
        if memory_content:
            sections.append(PromptSection(
                name="memory",
                content=memory_content,
                priority=Priority.MEMORY,
                required=False,
                metadata={"memory_count": len(ctx.memories)}
            ))

        # 5. 构建历史消息
        history_content = self._format_history(ctx.conversation_history)
        if history_content:
            sections.append(PromptSection(
                name="history",
                content=history_content,
                priority=Priority.HISTORY,
                required=False,
                metadata={"turn_count": len(ctx.conversation_history)}
            ))

        # 6. Token预算计算和调整
        sections = self.budget_manager.calculate_tokens(sections)
        sections, truncated = self.budget_manager.apply_budget(sections, ctx.max_tokens)

        # 7. 组装最终消息列表
        messages = self._assemble_messages(sections, ctx)

        # 统计
        total_tokens = sum(s.token_count for s in sections)
        budget_used = {s.name: s.token_count for s in sections}

        logger.info(
            "prompt_built",
            session_id=ctx.session_id,
            agent_type=ctx.agent_type,
            total_tokens=total_tokens,
            section_count=len(sections),
            truncated=truncated
        )

        return BuildResult(
            messages=messages,
            total_tokens=total_tokens,
            sections=[
                {
                    "name": s.name,
                    "priority": s.priority.name,
                    "tokens": s.token_count,
                    "required": s.required
                }
                for s in sections
            ],
            budget_used=budget_used,
            truncated=truncated
        )

    async def _load_system_prompt(self, ctx: PromptContext) -> str:
        """加载系统提示"""
        variables = {
            "agent_id": ctx.session_id,
            "session_id": ctx.session_id,
            **ctx.variables
        }

        try:
            template = self.loader.load("system/base", variables=variables)
            return template.get("content", "")
        except TemplateNotFoundError:
            logger.warning("system_template_not_found")
            return self._default_system_prompt()

    async def _load_agent_prompt(self, ctx: PromptContext) -> str:
        """加载代理提示"""
        template_name = self.AGENT_TEMPLATES.get(ctx.agent_type)
        if not template_name:
            return ""

        variables = {
            "agent_type": ctx.agent_type,
            **ctx.variables
        }

        try:
            template = self.loader.load(template_name, variables=variables)
            return template.get("content", "")
        except TemplateNotFoundError:
            logger.warning(
                "agent_template_not_found",
                agent_type=ctx.agent_type
            )
            return ""

    async def _build_tools_prompt(self, ctx: PromptContext) -> str:
        """构建工具提示"""
        if not ctx.available_tools:
            return ""

        # 格式化工具列表
        tool_lines = ["## Available Tools\n"]

        for tool in ctx.available_tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            schema = tool.get("input_schema", {})

            tool_lines.append(f"### {name}")
            if desc:
                tool_lines.append(f"{desc}")

            # 参数说明
            if schema and "properties" in schema:
                tool_lines.append("**Parameters:**")
                for param, details in schema["properties"].items():
                    param_desc = details.get("description", "")
                    required = param in schema.get("required", [])
                    req_marker = " (required)" if required else ""
                    tool_lines.append(f"- `{param}`{req_marker}: {param_desc}")

            tool_lines.append("")

        return "\n".join(tool_lines)

    async def _build_memory_prompt(self, ctx: PromptContext) -> str:
        """构建记忆提示"""
        if not ctx.memories and not ctx.project_context:
            return ""

        lines = []

        # 项目上下文
        if ctx.project_context:
            lines.append("## Project Context")
            lines.append(ctx.project_context)
            lines.append("")

        # 记忆
        if ctx.memories:
            lines.append("## Relevant Memories")
            for i, memory in enumerate(ctx.memories, 1):
                content = memory.get("content", memory.get("summary", ""))
                if content:
                    lines.append(f"{i}. {content}")
            lines.append("")

        return "\n".join(lines)

    def _format_history(self, history: list[dict[str, str]]) -> str:
        """格式化对话历史"""
        if not history:
            return ""

        lines = ["## Recent Conversation"]

        for turn in history[-10:]:  # 最多最近10轮
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            role_label = "User" if role == "user" else "Assistant"
            lines.append(f"**{role_label}**: {content[:200]}...")  # 截断长消息

        return "\n".join(lines)

    def _assemble_messages(
        self,
        sections: list[PromptSection],
        ctx: PromptContext
    ) -> list[dict[str, str]]:
        """组装最终消息列表"""
        messages = []

        # 系统消息（合并所有高优先级内容）
        system_parts = []
        for section in sections:
            if section.priority >= Priority.SYSTEM:
                system_parts.append(section.content)

        if system_parts:
            messages.append({
                "role": "system",
                "content": "\n\n".join(system_parts)
            })

        # 历史消息
        for turn in ctx.conversation_history:
            messages.append({
                "role": turn.get("role", "user"),
                "content": turn.get("content", "")
            })

        # 当前用户消息
        if ctx.user_message:
            messages.append({
                "role": "user",
                "content": ctx.user_message
            })

        return messages

    def _default_system_prompt(self) -> str:
        """默认系统提示"""
        return """You are CoPaw Code, an AI coding assistant.

## Your Role
Help users with coding tasks including:
- Writing and modifying code
- Debugging and testing
- Code review and optimization
- Documentation

## Guidelines
- Be clear and concise
- Explain your reasoning
- Validate changes before applying
- Ask for clarification when needed
"""

    def build_simple(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        max_tokens: int = 4096
    ) -> list[dict[str, str]]:
        """
        构建简单消息列表（无模板）
        
        用于快速构建简单对话场景
        """
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        return messages


# 便捷函数
async def build_prompt(
    session_id: str,
    user_message: str,
    agent_type: str = "main",
    **kwargs: Any
) -> BuildResult:
    """构建提示的便捷函数"""
    from .loader import get_loader

    loader = get_loader()
    builder = PromptBuilder(loader)

    ctx = PromptContext(
        session_id=session_id,
        user_message=user_message,
        agent_type=agent_type,
        **kwargs
    )

    return await builder.build(ctx)
