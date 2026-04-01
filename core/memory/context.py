"""
上下文管理 - 管理 LLM 上下文窗口和消息压缩
DEV-004 记忆系统组件
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

from core.llm.base import Message

logger = structlog.get_logger(__name__)


class ContextWindow(BaseModel):
    """上下文窗口配置"""
    max_tokens: int = 200000           # 最大上下文 token
    reserved_output_tokens: int = 8192  # 保留给输出的 token
    system_prompt_tokens: int = 2000    # 系统提示预估 token
    tools_tokens: int = 3000            # 工具定义预估 token

    @property
    def available_tokens(self) -> int:
        """可用于消息的 token 数"""
        return (
            self.max_tokens
            - self.reserved_output_tokens
            - self.system_prompt_tokens
            - self.tools_tokens
        )


class MessageSummary(BaseModel):
    """消息摘要"""
    turn_start: int        # 摘要起始轮次
    turn_end: int          # 摘要结束轮次
    summary: str           # 摘要内容
    key_points: list[str] = Field(default_factory=list)  # 关键点
    created_at: float = Field(default_factory=time.time)


class ContextManager:
    """
    上下文管理器
    
    功能：
    - Token 计数和预算管理
    - 消息压缩/摘要
    - 优先级保留策略
    - 自动触发压缩
    """

    def __init__(
        self,
        context_window: ContextWindow | None = None,
        tokenizer: Any = None,  # tiktoken 编码器
        compression_threshold: float = 0.8,  # 压缩阈值（占可用token比例）
    ) -> None:
        self._context_window = context_window or ContextWindow()
        self._tokenizer = tokenizer
        self._compression_threshold = compression_threshold
        self._summaries: list[MessageSummary] = []
        self._logger = logger.bind(component="ContextManager")

        # 尝试初始化 tokenizer
        if self._tokenizer is None:
            self._init_tokenizer()

    def _init_tokenizer(self) -> None:
        """初始化 tiktoken tokenizer"""
        try:
            import tiktoken
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self._logger.warning("tiktoken_not_available", using="estimate")
            self._tokenizer = None

    def count_tokens(self, text: str) -> int:
        """计算文本 token 数"""
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        else:
            # 估算：英文约 4 字符/token，中文约 2 字符/token
            # 保守估算
            return len(text) // 3 + 1

    def count_message_tokens(self, message: Message) -> int:
        """计算消息的 token 数"""
        content = message.content
        if isinstance(content, str):
            text = content
        else:
            # 结构化内容
            text = ""
            for block in content:
                if block.get("type") == "text":
                    text += block.get("text", "")
                elif block.get("type") == "tool_use":
                    text += block.get("name", "")
                    text += str(block.get("input", {}))

        # 加上 role 和其他元数据
        base_tokens = 4  # role + 基础格式
        return base_tokens + self.count_tokens(text)

    def count_messages_tokens(self, messages: list[Message]) -> int:
        """计算消息列表的 token 数"""
        return sum(self.count_message_tokens(m) for m in messages)

    def should_compress(self, messages: list[Message]) -> bool:
        """检查是否需要压缩"""
        current_tokens = self.count_messages_tokens(messages)
        threshold = self._context_window.available_tokens * self._compression_threshold
        return current_tokens > threshold

    def get_budget_status(self, messages: list[Message]) -> dict[str, Any]:
        """获取上下文预算状态"""
        current = self.count_messages_tokens(messages)
        available = self._context_window.available_tokens
        return {
            "current_tokens": current,
            "available_tokens": available,
            "used_percentage": round(current / available * 100, 1) if available > 0 else 0,
            "should_compress": self.should_compress(messages),
            "remaining_tokens": available - current,
        }

    def compress_messages(
        self,
        messages: list[Message],
        keep_recent: int = 4,  # 保留最近 N 轮对话
        keep_system: bool = True,  # 保留系统消息
    ) -> tuple[list[Message], MessageSummary]:
        """
        压缩消息历史
        
        返回：(压缩后的消息列表, 摘要对象)
        """
        if len(messages) <= keep_recent * 2 + (1 if keep_system else 0):
            # 不需要压缩
            return messages, MessageSummary(
                turn_start=0,
                turn_end=0,
                summary="No compression needed."
            )

        # 分离系统消息
        system_messages = []
        conversation_messages = []
        for msg in messages:
            if msg.role == "system":
                system_messages.append(msg)
            else:
                conversation_messages.append(msg)

        # 计算要压缩的消息
        total_turns = len([m for m in conversation_messages if m.role == "user"])
        compress_count = len(conversation_messages) - keep_recent * 2

        if compress_count <= 0:
            return messages, MessageSummary(
                turn_start=0,
                turn_end=0,
                summary="No compression needed."
            )

        # 提取要压缩的消息
        to_compress = conversation_messages[:compress_count]
        remaining = conversation_messages[compress_count:]

        # 生成摘要
        summary = self._generate_summary(to_compress, total_turns - keep_recent)

        # 创建摘要消息
        summary_message = Message(
            role="user",
            content=f"[Previous conversation summary]\n{summary.summary}"
        )

        # 记录摘要
        self._summaries.append(summary)

        # 组合结果
        result = system_messages + [summary_message] + remaining

        self._logger.info(
            "compressed_messages",
            original_count=len(messages),
            compressed_count=len(result),
            turns_compressed=summary.turn_end - summary.turn_start + 1,
        )

        return result, summary

    def _generate_summary(
        self,
        messages: list[Message],
        turns: int
    ) -> MessageSummary:
        """生成消息摘要（内部方法）"""
        # 提取关键信息
        key_points = []
        user_requests = []
        tool_calls = []
        results = []

        for msg in messages:
            if msg.role == "user":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                user_requests.append(content[:200])  # 截取前 200 字符
            elif msg.role == "assistant":
                if isinstance(msg.content, list):
                    for block in msg.content:
                        if block.get("type") == "tool_use":
                            tool_calls.append(block.get("name", ""))
            elif msg.role == "tool":
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                results.append(content[:100])

        # 生成摘要文本
        summary_parts = []

        if user_requests:
            summary_parts.append(f"User made {len(user_requests)} requests.")
            # 添加关键请求
            for i, req in enumerate(user_requests[:3]):
                summary_parts.append(f"  - Request {i+1}: {req[:100]}...")

        if tool_calls:
            unique_tools = list(set(tool_calls))
            summary_parts.append(f"Tools used: {', '.join(unique_tools)}")

        if results:
            summary_parts.append(f"Executed {len(results)} tool operations.")

        # 提取关键点
        for req in user_requests[:2]:
            if len(req) > 50:
                key_points.append(req[:100] + "...")
            else:
                key_points.append(req)

        return MessageSummary(
            turn_start=1,
            turn_end=turns,
            summary="\n".join(summary_parts),
            key_points=key_points,
        )

    def create_summary_prompt(self, messages: list[Message]) -> str:
        """创建摘要提示（用于 LLM 生成摘要）"""
        history_text = ""
        for msg in messages:
            role = msg.role.upper()
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            history_text += f"{role}: {content[:500]}\n\n"

        return f"""Please summarize the following conversation history concisely, 
preserving key information, decisions, and context needed for continuation.

CONVERSATION HISTORY:
{history_text}

Provide a concise summary (under 500 words) that captures:
1. Main user requests and goals
2. Key decisions made
3. Important context for continuing the work
4. Any unresolved questions or issues

SUMMARY:"""

    def optimize_context(
        self,
        messages: list[Message],
        max_tokens: int | None = None,
    ) -> list[Message]:
        """
        优化上下文，确保在 token 限制内
        
        策略：
        1. 检查是否超出限制
        2. 如果超出，按优先级移除旧消息
        3. 保留最近的重要消息
        """
        limit = max_tokens or self._context_window.available_tokens

        if self.count_messages_tokens(messages) <= limit:
            return messages

        # 需要压缩
        optimized, _ = self.compress_messages(messages)

        # 如果还是超限，更激进地移除
        while self.count_messages_tokens(optimized) > limit and len(optimized) > 2:
            # 移除最早的非系统消息
            for i, msg in enumerate(optimized):
                if msg.role != "system":
                    optimized = optimized[:i] + optimized[i+1:]
                    break

        return optimized

    @property
    def summaries(self) -> list[MessageSummary]:
        """获取所有摘要"""
        return self._summaries.copy()

    def clear_summaries(self) -> None:
        """清除摘要历史"""
        self._summaries.clear()
