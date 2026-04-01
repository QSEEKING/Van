"""
LLM Provider 工厂 & 适配器
"""
from __future__ import annotations

from typing import Any

from ..config import LLMProvider, get_settings
from .base import BaseLLMProvider


def create_llm_provider(
    provider: LLMProvider | str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """工厂方法：根据配置创建对应的 LLM Provider 实例"""
    settings = get_settings()

    if provider is None:
        provider = settings.default_provider
    if isinstance(provider, str):
        provider = LLMProvider(provider)

    if provider == LLMProvider.ANTHROPIC:
        from .anthropic import AnthropicProvider
        return AnthropicProvider(
            api_key=kwargs.pop("api_key", settings.anthropic_api_key),
            model=model or settings.default_model,
            **kwargs,
        )
    elif provider == LLMProvider.OPENAI:
        from .openai import OpenAIProvider
        return OpenAIProvider(
            api_key=kwargs.pop("api_key", settings.openai_api_key),
            model=model or "gpt-4o",
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
