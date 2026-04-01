"""
Security Package - 安全模块
包含：Security Monitor, Permission Manager, Sandbox Isolation
"""
from .monitor.security_monitor import SecurityCheckResult, SecurityLevel, SecurityMonitor
from .permission.manager import Permission, PermissionManager, PermissionRule
from .sandbox.isolator import SandboxConfig, SandboxIsolator, SandboxResult

# Singleton instance
_security_monitor_instance: SecurityMonitor | None = None


def get_security_monitor() -> SecurityMonitor:
    """Get the singleton SecurityMonitor instance"""
    global _security_monitor_instance
    if _security_monitor_instance is None:
        _security_monitor_instance = SecurityMonitor()
    return _security_monitor_instance


__all__ = [
    # Security Monitor
    "SecurityMonitor",
    "SecurityCheckResult",
    "SecurityLevel",
    "get_security_monitor",
    # Permission
    "PermissionManager",
    "Permission",
    "PermissionRule",
    # Sandbox
    "SandboxIsolator",
    "SandboxConfig",
    "SandboxResult",
]
