"""
Security Monitor - 独立安全监控器
作为独立的安全监控组件，负责实时安全检查和风险监控
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecurityLevel(Enum):
    """安全等级"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    passed: bool
    level: SecurityLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "recommendations": self.recommendations,
        }


class SecurityMonitor:
    """
    安全监控器 - 独立的安全监控组件
    
    职责：
    1. 命令注入检测
    2. 路径遍历检测
    3. 敏感信息泄露检测
    4. 危险操作拦截
    5. 实时安全审计日志
    """

    # 危险命令模式
    DANGEROUS_COMMANDS = {
        # 系统操作
        "rm -rf", "rm -r", "rmdir /s", "del /s", "format",
        "mkfs", "fdisk", "dd if=",
        # 权限提升
        "sudo", "su ", "chmod 777", "chmod -R 777",
        "chown root", "/etc/passwd", "/etc/shadow",
        # 网络危险操作
        "iptables", "ufw disable", "firewall-cmd --disable",
        # 进程操作
        "kill -9", "killall", "pkill -9",
        # 系统控制
        "shutdown", "reboot", "init 0", "init 6", "halt", "poweroff",
        # 包管理危险操作
        "pip uninstall -y", "npm uninstall -g",
        # Docker 危险操作
        "docker rm -f $(docker ps -aq)", "docker system prune -af",
    }

    # 命令注入模式
    INJECTION_PATTERNS = [
        r";\s*rm",           # ; rm
        r"\|\s*rm",          # | rm
        r"`[^`]*rm[^`]*`",   # `rm`
        r'\$\(.*rm.*\)',     # $(rm)
        r">\s*/etc/",        # > /etc/
        r"2>&1.*>",          # 重定向注入
        r"\|\s*bash",        # | bash
        r"\|\s*sh\b",        # | sh
        r"\|\s*zsh",         # | zsh
        r"\|\s*python",      # | python
        r"\|\s*perl",        # | perl
        r"\|\s*ruby",        # | ruby
    ]

    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",           # ../
        r"\.\.\\",          # ..\
        r"\.\.%2[fF]",      # ..%2f
        r"\.\.%5[cC]",      # ..%5c
        r"%2[eE]%2[eE]",    # %2e%2e
        r"\.\./etc/passwd",
        r"\.\./etc/shadow",
        r"\.\./\.ssh",
        r"\.\./\.env",
    ]

    # 敏感文件模式
    SENSITIVE_FILE_PATTERNS = [
        r"\.env$", r"\.env\.", r"credentials", r"secrets?",
        r"api[_-]?key", r"private[_-]?key", r"access[_-]?token",
        r"\.pem$", r"\.key$", r"\.p12$", r"\.pfx$",
        r"id_rsa", r"id_dsa", r"id_ecdsa", r"id_ed25519",
        r"\.git/config$", r"\.git-credentials",
        r"postgres\.pass", r"pgpass",
        r"\.npmrc$", r"\.pypirc$",
    ]

    # 敏感数据模式
    SENSITIVE_DATA_PATTERNS = [
        # API Keys
        (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[\w\-]{20,}['\"]?", "api_key"),
        (r"sk-[a-zA-Z0-9]{20,}", "openai_key"),
        (r"sk-ant-[a-zA-Z0-9\-]{20,}", "anthropic_key"),
        # AWS
        (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
        (r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*['\"]?[\w/+=]{40}['\"]?", "aws_secret"),
        # Generic secrets
        (r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"]?[^'\"]{8,}['\"]?", "secret"),
        # Tokens
        (r"(?i)(bearer|token)\s+[a-zA-Z0-9\-._~+/]+=*", "bearer_token"),
        # Private keys
        (r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "private_key"),
    ]

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode = strict_mode
        self._audit_log: list[dict[str, Any]] = []
        self._logger = logger.bind(component="security_monitor")

        # 编译正则表达式以提高性能
        self._injection_regex = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self._traversal_regex = [re.compile(p) for p in self.PATH_TRAVERSAL_PATTERNS]
        self._sensitive_file_regex = [re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_FILE_PATTERNS]
        self._sensitive_data_regex = [(re.compile(p), name) for p, name in self.SENSITIVE_DATA_PATTERNS]

    def check_command(self, command: str) -> SecurityCheckResult:
        """
        检查命令安全性
        
        Args:
            command: 要检查的命令字符串
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        issues: list[str] = []
        details: dict[str, Any] = {"command": command[:200]}  # 截断长命令
        recommendations: list[str] = []

        # 检查危险命令
        cmd_lower = command.lower()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous.lower() in cmd_lower:
                issues.append(f"Dangerous command detected: {dangerous}")
                recommendations.append(f"Avoid using '{dangerous}' or use with explicit confirmation")

        # 检查命令注入
        for pattern in self._injection_regex:
            if pattern.search(command):
                issues.append("Potential command injection detected")
                recommendations.append("Sanitize user input before using in shell commands")
                break

        # 检查管道链
        if "|" in command and any(d in cmd_lower for d in ["bash", "sh", "python", "perl"]):
            issues.append("Potentially dangerous pipe chain detected")
            recommendations.append("Review command chain for security risks")

        # 计算安全等级
        if not issues:
            result = SecurityCheckResult(
                passed=True,
                level=SecurityLevel.SAFE,
                message="Command passed security check",
                details=details,
            )
        else:
            # 根据问题严重程度确定等级
            if any(d in cmd_lower for d in ["rm -rf", "sudo", "chmod 777", "dd if="]):
                level = SecurityLevel.CRITICAL
            elif any(d in cmd_lower for d in ["rm -r", "shutdown", "reboot", "iptables"]):
                level = SecurityLevel.HIGH
            elif len(issues) > 2:
                level = SecurityLevel.HIGH
            elif len(issues) > 1:
                level = SecurityLevel.MEDIUM
            else:
                level = SecurityLevel.LOW

            result = SecurityCheckResult(
                passed=not self.strict_mode and level not in [SecurityLevel.CRITICAL, SecurityLevel.HIGH],
                level=level,
                message=f"Security issues found: {'; '.join(issues)}",
                details=details,
                recommendations=recommendations,
            )

        self._log_audit("command_check", result)
        return result

    def check_path(self, path: str, base_dir: str | None = None) -> SecurityCheckResult:
        """
        检查路径安全性
        
        Args:
            path: 要检查的路径
            base_dir: 基础目录（可选，用于验证路径是否在允许范围内）
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        issues: list[str] = []
        details: dict[str, Any] = {"path": path}
        recommendations: list[str] = []

        # 检查路径遍历
        for pattern in self._traversal_regex:
            if pattern.search(path):
                issues.append("Path traversal detected")
                recommendations.append("Use safe path join methods and validate paths")
                break

        # 检查敏感文件访问
        for pattern in self._sensitive_file_regex:
            if pattern.search(path):
                issues.append(f"Sensitive file access detected: {path}")
                recommendations.append("Verify if access to this sensitive file is necessary")
                break

        # 检查绝对路径访问系统目录
        if path.startswith(("/", "\\")):
            sensitive_dirs = ["/etc", "/root", "/home", "/var/log", "/proc", "/sys"]
            for sdir in sensitive_dirs:
                if path.startswith(sdir):
                    issues.append(f"Access to sensitive directory: {sdir}")
                    recommendations.append("Ensure this access is authorized and logged")
                    break

        # 如果提供了基础目录，验证路径是否在允许范围内
        if base_dir and not issues:
            import os
            try:
                real_path = os.path.realpath(path)
                real_base = os.path.realpath(base_dir)
                if not real_path.startswith(real_base):
                    issues.append("Path escapes base directory")
                    recommendations.append("Ensure path stays within allowed directory")
            except Exception as e:
                issues.append(f"Path validation error: {e}")

        if not issues:
            result = SecurityCheckResult(
                passed=True,
                level=SecurityLevel.SAFE,
                message="Path passed security check",
                details=details,
            )
        else:
            level = SecurityLevel.HIGH if "traversal" in " ".join(issues).lower() else SecurityLevel.MEDIUM
            result = SecurityCheckResult(
                passed=False if self.strict_mode or "traversal" in " ".join(issues).lower() else True,
                level=level,
                message=f"Path security issues: {'; '.join(issues)}",
                details=details,
                recommendations=recommendations,
            )

        self._log_audit("path_check", result)
        return result

    def check_content(self, content: str, content_type: str = "text") -> SecurityCheckResult:
        """
        检查内容中的敏感信息
        
        Args:
            content: 要检查的内容
            content_type: 内容类型（text, code, config等）
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        issues: list[str] = []
        details: dict[str, Any] = {"content_type": content_type}
        recommendations: list[str] = []
        found_secrets: list[dict[str, str]] = []

        # 检查敏感数据模式
        for pattern, secret_type in self._sensitive_data_regex:
            matches = pattern.findall(content)
            if matches:
                found_secrets.append({
                    "type": secret_type,
                    "count": len(matches),
                    "sample": matches[0][:20] + "..." if len(matches[0]) > 20 else matches[0],
                })

        if found_secrets:
            issues.append(f"Sensitive data patterns detected: {len(found_secrets)} types")
            details["found_secrets"] = found_secrets
            recommendations.extend([
                "Remove hardcoded secrets from code",
                "Use environment variables or secret management systems",
                "Add sensitive files to .gitignore",
            ])

        if not issues:
            result = SecurityCheckResult(
                passed=True,
                level=SecurityLevel.SAFE,
                message="Content passed security check",
                details=details,
            )
        else:
            level = SecurityLevel.HIGH if len(found_secrets) > 2 else SecurityLevel.MEDIUM
            result = SecurityCheckResult(
                passed=True,  # 内容检查不阻止，仅警告
                level=level,
                message=f"Sensitive content detected: {'; '.join(issues)}",
                details=details,
                recommendations=recommendations,
            )

        self._log_audit("content_check", result)
        return result

    def check_operation(
        self,
        operation: str,
        target: str,
        context: dict[str, Any] | None = None,
    ) -> SecurityCheckResult:
        """
        通用操作安全检查
        
        Args:
            operation: 操作类型（read, write, execute, delete等）
            target: 操作目标
            context: 额外上下文
            
        Returns:
            SecurityCheckResult: 安全检查结果
        """
        context = context or {}

        # 根据操作类型分发检查
        if operation in ("execute", "run", "shell"):
            return self.check_command(target)
        elif operation in ("read", "write", "delete", "modify"):
            return self.check_path(target)
        elif operation in ("upload", "download", "content"):
            return self.check_content(target)
        else:
            return SecurityCheckResult(
                passed=True,
                level=SecurityLevel.SAFE,
                message=f"Operation '{operation}' passed basic security check",
                details={"operation": operation, "target": target[:200]},
            )

    def _log_audit(self, check_type: str, result: SecurityCheckResult) -> None:
        """记录审计日志"""
        log_entry = {
            "check_type": check_type,
            "passed": result.passed,
            "level": result.level.value,
            "message": result.message,
            "timestamp": self._get_timestamp(),
        }
        self._audit_log.append(log_entry)

        # 结构化日志
        if not result.passed or result.level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            self._logger.warning("security_check_failed", **log_entry)
        else:
            self._logger.debug("security_check_passed", **log_entry)

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]

    def clear_audit_log(self) -> None:
        """清空审计日志"""
        self._audit_log.clear()
        self._logger.info("audit_log_cleared")

    def sanitize_input(self, input_str: str) -> str:
        """
        清理输入字符串，移除潜在的危险内容
        
        Args:
            input_str: 要清理的输入字符串
            
        Returns:
            清理后的字符串
        """
        import html
        # HTML转义
        sanitized = html.escape(input_str)
        # 移除危险字符
        dangerous_chars = ["<", ">", "'", '"', ";", "|", "&", "$", "`", "\n", "\r"]
        for char in dangerous_chars:
            if char in ["<", ">", "'", '"', ";", "|", "&", "$", "`"]:
                # 已经被html.escape处理了
                continue
            sanitized = sanitized.replace(char, "")
        return sanitized

    def get_stats(self) -> dict[str, Any]:
        """获取安全检查统计信息"""
        total = len(self._audit_log)
        blocked = sum(1 for log in self._audit_log if not log["passed"])
        return {
            "total_checks": total,
            "blocked": blocked,
            "passed": total - blocked,
            "block_rate": blocked / total * 100 if total > 0 else 0,
        }

    def get_security_report(self) -> dict[str, Any]:
        """生成安全报告"""
        total_checks = len(self._audit_log)
        failed_checks = sum(1 for log in self._audit_log if not log["passed"])
        by_level: dict[str, int] = {}
        for log in self._audit_log:
            level = log["level"]
            by_level[level] = by_level.get(level, 0) + 1

        return {
            "total_checks": total_checks,
            "failed_checks": failed_checks,
            "pass_rate": (total_checks - failed_checks) / total_checks * 100 if total_checks > 0 else 100,
            "by_level": by_level,
            "recent_failures": [log for log in self._audit_log[-10:] if not log["passed"]],
        }


# 创建全局单例
_security_monitor: SecurityMonitor | None = None


def get_security_monitor(strict_mode: bool = False) -> SecurityMonitor:
    """获取全局安全监控器实例"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor(strict_mode=strict_mode)
    return _security_monitor
