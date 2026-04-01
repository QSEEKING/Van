"""
代理协调器 - 管理主代理与子代理的调度和结果聚合
"""
from __future__ import annotations

from typing import Any

import structlog

from core.llm.base import BaseLLMProvider
from tools.base import ToolRegistry

from .sub_agents.base import BaseSubAgent, SubAgentInput, SubAgentOutput
from .sub_agents.batch import BatchAgent
from .sub_agents.explore import ExploreAgent
from .sub_agents.plan import PlanAgent
from .sub_agents.review import ReviewAgent
from .sub_agents.verify import VerifyAgent

logger = structlog.get_logger(__name__)


class AgentCoordinator:
    """
    代理协调器：
    - 管理子代理的注册和调度
    - 根据任务类型选择合适的子代理
    - 聚合多个子代理的结果
    - 集成独立 Security Monitor 进行安全检查
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.llm = llm
        self.registry = tool_registry or ToolRegistry.get_instance()
        self._agents: dict[str, BaseSubAgent] = {}
        self._logger = logger.bind(component="coordinator")

        # 延迟导入 Security Monitor 避免循环依赖
        self._security_monitor = None
        self._register_default_agents()

    @property
    def security_monitor(self):
        """获取安全监控器（延迟加载）"""
        if self._security_monitor is None:
            from security import get_security_monitor
            self._security_monitor = get_security_monitor()
        return self._security_monitor

    def _register_default_agents(self) -> None:
        """注册默认子代理"""
        defaults: list[BaseSubAgent] = [
            ExploreAgent(self.llm, self.registry),
            PlanAgent(self.llm),
            VerifyAgent(self.llm, self.registry),
            ReviewAgent(self.llm, self.registry),
            BatchAgent(self.llm, self.registry),
        ]
        for agent in defaults:
            self.register(agent)

    def register(self, agent: BaseSubAgent) -> None:
        """注册子代理"""
        self._agents[agent.agent_type] = agent
        self._logger.debug("agent_registered", agent_type=agent.agent_type)

    def unregister(self, agent_type: str) -> bool:
        """注销子代理"""
        if agent_type in self._agents:
            del self._agents[agent_type]
            self._logger.debug("agent_unregistered", agent_type=agent_type)
            return True
        return False

    def get_agent(self, agent_type: str) -> BaseSubAgent | None:
        """获取指定类型的子代理"""
        return self._agents.get(agent_type)

    def list_agents(self) -> list[dict[str, str]]:
        """列出所有注册的子代理"""
        return [
            {"type": a.agent_type, "description": a.description}
            for a in self._agents.values()
        ]

    async def invoke(
        self,
        agent_type: str,
        task: str,
        context: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SubAgentOutput:
        """调用指定类型的子代理"""
        agent = self.get_agent(agent_type)
        if agent is None:
            return SubAgentOutput(
                agent_type=agent_type,
                result="",
                success=False,
                error=f"Unknown agent type: '{agent_type}'. "
                      f"Available: {list(self._agents.keys())}",
            )

        self._logger.info("invoking_sub_agent", agent_type=agent_type)
        input_obj = SubAgentInput(
            task=task,
            context=context,
            metadata=metadata or {},
        )
        return await agent.run(input_obj)

    async def invoke_parallel(
        self,
        requests: list[dict[str, Any]],
    ) -> list[SubAgentOutput]:
        """
        并发调用多个子代理
        requests: [{"agent_type": str, "task": str, "context": str}, ...]
        """
        import asyncio
        tasks = [
            self.invoke(
                agent_type=r["agent_type"],
                task=r["task"],
                context=r.get("context", ""),
                metadata=r.get("metadata"),
            )
            for r in requests
        ]
        return await asyncio.gather(*tasks)

    def check_security(
        self,
        operation: str,
        target: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """
        使用 Security Monitor 进行安全检查
        
        Args:
            operation: 操作类型（execute, read, write, delete等）
            target: 操作目标
            context: 额外上下文
            
        Returns:
            (是否允许, 原因说明)
        """
        result = self.security_monitor.check_operation(operation, target, context)
        return result.passed, result.message

    def aggregate_results(self, outputs: list[SubAgentOutput]) -> str:
        """聚合多个子代理输出为统一字符串"""
        parts = []
        for output in outputs:
            if output.success:
                parts.append(
                    f"## [{output.agent_type.upper()} Agent]\n{output.result}"
                )
            else:
                parts.append(
                    f"## [{output.agent_type.upper()} Agent - ERROR]\n{output.error}"
                )
        return "\n\n---\n\n".join(parts)

    def get_statistics(self) -> dict[str, Any]:
        """获取协调器统计信息"""
        return {
            "registered_agents": list(self._agents.keys()),
            "total_agents": len(self._agents),
            "security_monitor_active": self._security_monitor is not None,
        }
