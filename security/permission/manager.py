"""
Permission Manager - 权限管理器
实现细粒度的权限控制和访问控制列表
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from enum import Enum, IntFlag
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Permission(IntFlag):
    """权限类型 - 支持位运算组合"""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 4
    DELETE = 8
    ADMIN = 16

    # 预定义组合
    READ_WRITE = READ | WRITE
    READ_WRITE_DELETE = READ | WRITE | DELETE
    FULL = READ | WRITE | EXECUTE | DELETE | ADMIN

    def __contains__(self, other: "Permission") -> bool:
        return (self.value & other.value) == other.value


@dataclass
class PermissionRule:
    """
    权限规则
    
    Attributes:
        resource: 资源路径模式（支持通配符）
        permissions: 允许的权限组合
        conditions: 额外条件（如时间限制、IP限制等）
        priority: 规则优先级（数字越大优先级越高）
    """
    resource: str
    permissions: Permission
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def matches(self, resource: str) -> bool:
        """检查资源是否匹配此规则"""
        # 支持通配符匹配
        return fnmatch.fnmatch(resource, self.resource) or resource.startswith(self.resource.rstrip("*"))


@dataclass
class CheckResult:
    """权限检查结果"""
    allowed: bool
    reason: str
    resource: str = ""
    permission: Permission = Permission.NONE


class Role(Enum):
    """用户角色"""
    USER = "user"
    DEVELOPER = "developer"
    ADMIN = "admin"

    def get_default_permissions(self) -> Permission:
        """获取角色默认权限"""
        if self == Role.USER:
            return Permission.READ
        elif self == Role.DEVELOPER:
            return Permission.READ | Permission.WRITE
        elif self == Role.ADMIN:
            return Permission.FULL
        return Permission.NONE


class PermissionManager:
    """
    权限管理器
    
    功能：
    1. 基于角色的访问控制 (RBAC)
    2. 资源权限检查
    3. 权限规则管理
    4. 审计日志
    """

    # 默认安全权限模板
    DEFAULT_RULES = [
        # 源代码目录 - 允许读写
        PermissionRule("src/**", Permission.READ | Permission.WRITE, priority=10),
        PermissionRule("lib/**", Permission.READ | Permission.WRITE, priority=10),
        PermissionRule("copaw-code/**", Permission.READ | Permission.WRITE, priority=10),
        # 工作目录 - 允许读写
        PermissionRule("workspace/**", Permission.READ | Permission.WRITE | Permission.DELETE, priority=5),
        PermissionRule("work/**", Permission.READ | Permission.WRITE | Permission.DELETE, priority=5),
        # 敏感文件 - 禁止访问
        PermissionRule("**/.env", Permission.NONE, priority=100),
        PermissionRule("**/.ssh/**", Permission.NONE, priority=100),
        PermissionRule("**/credentials*", Permission.NONE, priority=100),
        PermissionRule("**/secrets*", Permission.NONE, priority=100),
        PermissionRule("**/*.pem", Permission.NONE, priority=100),
        PermissionRule("**/*.key", Permission.NONE, priority=100),
        # 系统目录 - 只读
        PermissionRule("/etc/**", Permission.READ, priority=50),
        PermissionRule("/usr/**", Permission.READ, priority=50),
        # 禁止执行的目录
        PermissionRule("/bin/**", Permission.READ, priority=50),
        PermissionRule("/sbin/**", Permission.READ, priority=50),
    ]

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode = strict_mode
        self._rules: list[PermissionRule] = list(self.DEFAULT_RULES)
        self._role_permissions: dict[str, set[Permission]] = {}
        self._audit_log: list[dict[str, Any]] = []
        self._logger = logger.bind(component="permission_manager")

    def add_rule(self, rule: PermissionRule) -> None:
        """添加权限规则"""
        self._rules.append(rule)
        # 按优先级排序（高优先级在前）
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        self._logger.debug("rule_added", resource=rule.resource, permissions=rule.permissions.value)

    def remove_rule(self, resource: str) -> bool:
        """移除指定资源的权限规则"""
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.resource != resource]
        return len(self._rules) < initial_count

    def clear_custom_rules(self) -> None:
        """清除所有自定义规则（保留默认规则）"""
        self._rules = list(self.DEFAULT_RULES)

    def check_permission(
        self,
        resource: str,
        permission: Permission,
        context: dict[str, Any] | None = None,
    ) -> CheckResult:
        """
        检查是否具有指定权限
        
        Args:
            resource: 资源路径
            permission: 请求的权限
            context: 额外上下文信息
            
        Returns:
            CheckResult 对象
        """
        context = context or {}

        # 规范化路径
        normalized_resource = self._normalize_path(resource)

        # 遍历规则（按优先级顺序）
        for rule in self._rules:
            if rule.matches(normalized_resource):
                if permission in rule.permissions:
                    # 检查额外条件
                    if self._check_conditions(rule.conditions, context):
                        self._log_access(normalized_resource, permission, True, f"Rule: {rule.resource}")
                        return CheckResult(True, f"Allowed by rule: {rule.resource}", normalized_resource, permission)
                else:
                    # 找到匹配规则但权限不足
                    self._log_access(normalized_resource, permission, False, f"Rule denies: {rule.resource}")
                    return CheckResult(False, f"Permission denied by rule: {rule.resource}", normalized_resource, permission)

        # 没有匹配规则，使用默认策略
        if self.strict_mode:
            self._log_access(normalized_resource, permission, False, "No matching rule (strict mode)")
            return CheckResult(False, "No matching permission rule found (strict mode)", normalized_resource, permission)
        else:
            self._log_access(normalized_resource, permission, True, "Default allow (non-strict mode)")
            return CheckResult(True, "Default allow (no matching rule)", normalized_resource, permission)

    def _normalize_path(self, path: str) -> str:
        """规范化路径"""
        # 转换为绝对路径
        if not os.path.isabs(path):
            path = os.path.abspath(path)

        # 解析符号链接和相对路径
        try:
            path = os.path.realpath(path)
        except Exception:
            pass

        # 确保路径以 / 开头（统一使用 Unix 风格）
        return path.replace("\\", "/")

    def _check_conditions(self, conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        """检查额外条件"""
        if not conditions:
            return True

        # 时间限制检查
        if "time_range" in conditions:
            # TODO: 实现时间范围检查
            pass

        # IP 白名单检查
        if "allowed_ips" in conditions:
            client_ip = context.get("client_ip")
            if client_ip and client_ip not in conditions["allowed_ips"]:
                return False

        # 其他条件...

        return True

    def _log_access(
        self,
        resource: str,
        permission: Permission,
        granted: bool,
        reason: str,
    ) -> None:
        """记录访问日志"""
        log_entry = {
            "resource": resource,
            "permission": permission.name,
            "granted": granted,
            "reason": reason,
            "timestamp": self._get_timestamp(),
        }
        self._audit_log.append(log_entry)

        if granted:
            self._logger.debug("permission_granted", **log_entry)
        else:
            self._logger.warning("permission_denied", **log_entry)

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def grant_role_permission(self, role: str, permission: Permission) -> None:
        """为角色授予权限"""
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        self._role_permissions[role].add(permission)
        self._logger.info("role_permission_granted", role=role, permission=permission.name)

    def revoke_role_permission(self, role: str, permission: Permission) -> None:
        """撤销角色权限"""
        if role in self._role_permissions and permission in self._role_permissions[role]:
            self._role_permissions[role].remove(permission)
            self._logger.info("role_permission_revoked", role=role, permission=permission.name)

    def check_role_permission(self, role: str, permission: Permission) -> bool:
        """检查角色是否具有指定权限"""
        if role not in self._role_permissions:
            return False
        return permission in self._role_permissions[role]

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]

    def get_role_permissions(self, role: Role) -> Permission:
        """获取角色的权限"""
        if isinstance(role, Role):
            return role.get_default_permissions()
        return self._role_permissions.get(str(role), Permission.NONE)

    def get_permissions(self, resource: str) -> Permission:
        """获取资源的权限"""
        for rule in self._rules:
            if rule.matches(resource):
                return rule.permissions
        # 默认只读权限
        return Permission.READ

    def get_permission_report(self) -> dict[str, Any]:
        """生成权限报告"""
        total_checks = len(self._audit_log)
        denied_checks = sum(1 for log in self._audit_log if not log["granted"])

        return {
            "total_checks": total_checks,
            "denied_checks": denied_checks,
            "rules_count": len(self._rules),
            "roles_count": len(self._role_permissions),
            "recent_denials": [log for log in self._audit_log[-10:] if not log["granted"]],
        }


# 创建全局单例
_permission_manager: PermissionManager | None = None


def get_permission_manager(strict_mode: bool = False) -> PermissionManager:
    """获取全局权限管理器实例"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(strict_mode=strict_mode)
    return _permission_manager
