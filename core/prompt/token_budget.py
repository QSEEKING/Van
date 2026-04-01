"""
Token预算管理 - DEV-002 提示管理系统

功能：
- 精确Token计数 (tiktoken)
- 预算分配策略
- 内容截断和裁剪
- 预算优化算法
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# 尝试导入tiktoken，如果失败则使用估算
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken_not_available_using_estimation")


class TruncateStrategy(Enum):
    """截断策略"""
    PRIORITY = "priority"      # 按优先级裁剪
    OLDEST_FIRST = "oldest"    # 最旧的先裁剪
    SMART = "smart"            # 智能裁剪（保留关键信息）


@dataclass
class BudgetConfig:
    """预算配置"""
    max_tokens: int = 4096
    reserved_response_ratio: float = 0.25  # 25%预留给响应
    min_system_tokens: int = 500
    min_tools_tokens: int = 200
    min_memory_tokens: int = 100
    min_history_tokens: int = 200
    truncate_strategy: TruncateStrategy = TruncateStrategy.PRIORITY

    @property
    def available_for_content(self) -> int:
        """可用于内容的Token数量"""
        return int(self.max_tokens * (1 - self.reserved_response_ratio))

    @property
    def reserved_for_response(self) -> int:
        """预留给响应的Token数量"""
        return int(self.max_tokens * self.reserved_response_ratio)


@dataclass
class BudgetAllocation:
    """预算分配结果"""
    system: int = 0
    agent: int = 0
    tools: int = 0
    memory: int = 0
    history: int = 0
    user: int = 0
    reserved: int = 0

    @property
    def total(self) -> int:
        return self.system + self.agent + self.tools + self.memory + self.history + self.user

    def to_dict(self) -> dict[str, int]:
        return {
            "system": self.system,
            "agent": self.agent,
            "tools": self.tools,
            "memory": self.memory,
            "history": self.history,
            "user": self.user,
            "reserved": self.reserved,
            "total": self.total
        }


class TokenCounter:
    """Token计数器
    
    使用tiktoken进行精确计数，如果不可用则使用字符估算
    """

    # 模型到编码器的映射
    MODEL_ENCODINGS = {
        # Claude系列使用cl100k_base
        "claude-": "cl100k_base",
        # GPT系列
        "gpt-4": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
    }

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._encoding = self._get_encoding(model)

    def _get_encoding(self, model: str):
        """获取编码器"""
        if not TIKTOKEN_AVAILABLE:
            return None

        # 根据模型选择编码
        encoding_name = "cl100k_base"  # 默认

        for model_prefix, enc_name in self.MODEL_ENCODINGS.items():
            if model.lower().startswith(model_prefix):
                encoding_name = enc_name
                break

        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning("tiktoken_encoding_failed", error=str(e))
            return None

    def count(self, text: str) -> int:
        """计算文本的Token数量"""
        if not text:
            return 0

        if self._encoding is not None:
            try:
                return len(self._encoding.encode(text))
            except Exception:
                pass

        # 回退到估算：平均每4个字符约1个token
        return len(text) // 4 + 1

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """计算消息列表的Token数量"""
        # 每个消息有固定开销
        overhead_per_message = 4
        total = 0

        for msg in messages:
            total += overhead_per_message
            if "content" in msg:
                total += self.count(msg["content"])
            if "role" in msg:
                total += 1  # role的token

        return total

    def truncate(
        self,
        text: str,
        max_tokens: int,
        suffix: str = "\n\n[truncated...]"
    ) -> str:
        """截断文本到指定Token数量"""
        if not text:
            return text

        current_tokens = self.count(text)
        if current_tokens <= max_tokens:
            return text

        # 如果有tiktoken，精确截断
        if self._encoding is not None:
            try:
                tokens = self._encoding.encode(text)
                suffix_tokens = self.count(suffix)
                truncated_tokens = tokens[:max_tokens - suffix_tokens]
                return self._encoding.decode(truncated_tokens) + suffix
            except Exception:
                pass

        # 回退到字符估算截断
        max_chars = (max_tokens - self.count(suffix)) * 4
        if len(text) > max_chars:
            return text[:max_chars] + suffix
        return text


class TokenBudgetManager:
    """Token预算管理器
    
    功能：
    1. 计算各部分Token数量
    2. 应用预算策略
    3. 智能裁剪和优化
    """

    def __init__(self, config: BudgetConfig | None = None):
        self.config = config or BudgetConfig()
        self.counter = TokenCounter()

    def calculate_tokens(
        self,
        sections: list[Any]
    ) -> list[Any]:
        """计算每个部分的Token数量"""
        for section in sections:
            if hasattr(section, 'content'):
                section.token_count = self.counter.count(section.content)
            elif isinstance(section, dict):
                content = section.get('content', '')
                section['token_count'] = self.counter.count(content)

        return sections

    def apply_budget(
        self,
        sections: list[Any],
        max_tokens: int | None = None
    ) -> tuple[list[Any], bool]:
        """
        应用预算策略
        
        Args:
            sections: 提示片段列表
            max_tokens: 最大Token限制（覆盖配置）
            
        Returns:
            (调整后的片段列表, 是否进行了截断)
        """
        max_tokens = max_tokens or self.config.max_tokens
        available = int(max_tokens * (1 - self.config.reserved_response_ratio))

        # 计算当前总Token
        current_total = sum(
            s.token_count if hasattr(s, 'token_count') else s.get('token_count', 0)
            for s in sections
        )

        if current_total <= available:
            return sections, False

        # 需要裁剪
        logger.info(
            "budget_exceeded_applying_truncation",
            current=current_total,
            available=available
        )

        # 按优先级排序（低优先级先被裁剪）
        sorted_sections = sorted(sections, key=lambda s: (
            s.priority if hasattr(s, 'priority') else s.get('priority', 50),
            -getattr(s, 'token_count', s.get('token_count', 0))  # Token多的先裁剪
        ), reverse=True)

        result = []
        current = 0
        truncated = False

        for section in sorted_sections:
            token_count = section.token_count if hasattr(section, 'token_count') else section.get('token_count', 0)
            required = section.required if hasattr(section, 'required') else section.get('required', True)

            if current + token_count <= available:
                # 完全包含
                result.append(section)
                current += token_count
            elif required:
                # 必需部分，必须包含（可能需要截断内容）
                remaining = available - current
                if remaining > 100:  # 最小阈值
                    content = section.content if hasattr(section, 'content') else section.get('content', '')
                    truncated_content = self.counter.truncate(content, remaining)
                    if hasattr(section, 'content'):
                        section.content = truncated_content
                    else:
                        section['content'] = truncated_content
                    new_tokens = self.counter.count(truncated_content)
                    if hasattr(section, 'token_count'):
                        section.token_count = new_tokens
                    else:
                        section['token_count'] = new_tokens
                    result.append(section)
                    current += new_tokens
                    truncated = True
            else:
                # 非必需部分，尝试截断或跳过
                remaining = available - current
                if remaining > 200:  # 值得保留的阈值
                    content = section.content if hasattr(section, 'content') else section.get('content', '')
                    truncated_content = self.counter.truncate(content, remaining)
                    if hasattr(section, 'content'):
                        section.content = truncated_content
                    else:
                        section['content'] = truncated_content
                    new_tokens = self.counter.count(truncated_content)
                    if hasattr(section, 'token_count'):
                        section.token_count = new_tokens
                    else:
                        section['token_count'] = new_tokens
                    result.append(section)
                    current += new_tokens
                    truncated = True
                # 否则直接跳过

        return result, truncated

    def allocate_budget(
        self,
        system_tokens: int,
        agent_tokens: int,
        tool_tokens: int,
        memory_tokens: int,
        history_tokens: int,
        user_tokens: int = 0
    ) -> BudgetAllocation:
        """分配预算"""
        available = self.config.available_for_content
        reserved = self.config.reserved_for_response

        # 计算各部分实际分配
        allocation = BudgetAllocation(reserved=reserved)

        # 系统提示（必需）
        allocation.system = min(
            system_tokens,
            self.config.min_system_tokens + (system_tokens if system_tokens <= self.config.min_system_tokens else 0)
        )

        # 代理提示
        allocation.agent = agent_tokens

        # 工具提示
        allocation.tools = min(tool_tokens, self.config.min_tools_tokens * 2)

        # 记忆
        allocation.memory = min(memory_tokens, self.config.min_memory_tokens * 3)

        # 历史
        allocation.history = min(history_tokens, self.config.min_history_tokens * 5)

        # 用户消息
        allocation.user = user_tokens

        # 检查是否超预算
        if allocation.total > available:
            # 按优先级裁剪
            allocation = self._reduce_allocation(allocation, available)

        return allocation

    def _reduce_allocation(
        self,
        allocation: BudgetAllocation,
        target: int
    ) -> BudgetAllocation:
        """减少预算分配"""
        current = allocation.total
        over = current - target

        # 按优先级从低到高裁剪
        # 1. 先裁剪历史
        if allocation.history > self.config.min_history_tokens and over > 0:
            reduce_by = min(allocation.history - self.config.min_history_tokens, over)
            allocation.history -= reduce_by
            over -= reduce_by

        # 2. 裁剪记忆
        if allocation.memory > self.config.min_memory_tokens and over > 0:
            reduce_by = min(allocation.memory - self.config.min_memory_tokens, over)
            allocation.memory -= reduce_by
            over -= reduce_by

        # 3. 裁剪工具
        if allocation.tools > self.config.min_tools_tokens and over > 0:
            reduce_by = min(allocation.tools - self.config.min_tools_tokens, over)
            allocation.tools -= reduce_by
            over -= reduce_by

        return allocation

    def get_stats(self, sections: list[Any]) -> dict[str, Any]:
        """获取统计信息"""
        total = 0
        by_section = {}

        for section in sections:
            name = section.name if hasattr(section, 'name') else section.get('name', 'unknown')
            tokens = section.token_count if hasattr(section, 'token_count') else section.get('token_count', 0)
            by_section[name] = tokens
            total += tokens

        return {
            "total_tokens": total,
            "by_section": by_section,
            "max_tokens": self.config.max_tokens,
            "available": self.config.available_for_content,
            "utilization": total / self.config.max_tokens if self.config.max_tokens > 0 else 0
        }


def estimate_tokens(text: str) -> int:
    """便捷函数：估算文本Token数量"""
    counter = TokenCounter()
    return counter.count(text)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """便捷函数：估算消息列表Token数量"""
    counter = TokenCounter()
    return counter.count_messages(messages)
