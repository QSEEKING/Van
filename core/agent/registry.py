"""
代理注册表 - 管理代理类型到实现的映射
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.llm.base import BaseLLMProvider


class AgentRegistry:
    """代理注册表：维护代理类型 → 工厂函数的映射"""

    _instance: AgentRegistry | None = None
    _factories: dict = {}

    @classmethod
    def get_instance(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_factory(self, agent_type: str, factory) -> None:
        self._factories[agent_type] = factory

    def create(self, agent_type: str, llm: BaseLLMProvider, **kwargs):
        factory = self._factories.get(agent_type)
        if factory is None:
            raise ValueError(f"No factory registered for agent type: '{agent_type}'")
        return factory(llm, **kwargs)

    def list_types(self) -> list[str]:
        return list(self._factories.keys())
