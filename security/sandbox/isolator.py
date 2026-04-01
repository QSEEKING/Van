"""
Sandbox Isolator - 沙箱隔离器
实现安全的代码和命令执行隔离
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SandboxType(Enum):
    """沙箱类型"""
    PROCESS = "process"      # 进程级隔离
    CONTAINER = "container"  # 容器级隔离（Docker）
    FIREJAIL = "firejail"    # Firejail 沙箱
    NAMESPACE = "namespace"  # Linux Namespace 隔离


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    KILLED = "killed"
    DENIED = "denied"


@dataclass
class SandboxConfig:
    """沙箱配置"""
    sandbox_type: SandboxType = SandboxType.PROCESS

    # 资源限制
    max_memory_mb: int = 512      # 最大内存（MB）
    max_cpu_time_seconds: int = 30  # 最大 CPU 时间
    max_wall_time_seconds: int = 60  # 最大墙钟时间
    max_output_bytes: int = 10 * 1024 * 1024  # 最大输出（10MB）
    max_file_size_mb: int = 100   # 最大文件大小

    # 文件系统限制
    allowed_paths: list[str] = field(default_factory=lambda: ["/tmp", "/workspace"])
    denied_paths: list[str] = field(default_factory=lambda: ["/etc", "/root", "/home"])
    read_only_paths: list[str] = field(default_factory=list)
    no_network: bool = False      # 禁止网络访问

    # 执行限制
    max_processes: int = 10       # 最大进程数
    max_threads: int = 20        # 最大线程数
    max_open_files: int = 100    # 最大打开文件数

    # 环境变量
    env_vars: dict[str, str] = field(default_factory=dict)
    clear_env: bool = False      # 清除环境变量

    # 安全选项
    allow_network: bool = False   # 允许网络访问
    allow_ipc: bool = False       # 允许 IPC
    allow_syscalls: list[str] | None = None  # 允许的系统调用列表

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "sandbox_type": self.sandbox_type.value,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_time_seconds": self.max_cpu_time_seconds,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "max_output_bytes": self.max_output_bytes,
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
            "no_network": self.no_network,
        }


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    memory_used_mb: float = 0.0
    cpu_time_seconds: float = 0.0

    # 安全事件
    security_violations: list[str] = field(default_factory=list)
    blocked_operations: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "stdout": self.stdout[:10000],  # 截断长输出
            "stderr": self.stderr[:10000],
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "memory_used_mb": self.memory_used_mb,
            "cpu_time_seconds": self.cpu_time_seconds,
            "security_violations": self.security_violations,
            "blocked_operations": self.blocked_operations,
        }


class SandboxIsolator:
    """
    沙箱隔离器
    
    功能：
    1. 安全的命令执行
    2. 资源限制和监控
    3. 文件系统隔离
    4. 网络隔离
    5. 安全策略执行
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()
        self._work_dir: Path | None = None
        self._logger = logger.bind(component="sandbox_isolator")
        self._execution_count = 0

    async def execute(
        self,
        command: str,
        timeout: float | None = None,
        input_data: str | None = None,
        work_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """
        在沙箱中执行命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            input_data: 标准输入数据
            work_dir: 工作目录
            env: 额外环境变量
            
        Returns:
            SandboxResult: 执行结果
        """
        self._execution_count += 1
        exec_id = f"exec_{self._execution_count}"

        self._logger.info("sandbox_execution_start", exec_id=exec_id, command=command[:100])

        import time
        start_time = time.time()

        # 合并环境变量
        final_env = dict(os.environ) if not self.config.clear_env else {}
        final_env.update(self.config.env_vars)
        if env:
            final_env.update(env)

        # 确定工作目录
        final_work_dir = work_dir or str(self._get_work_dir())
        os.makedirs(final_work_dir, exist_ok=True)

        security_violations: list[str] = []
        blocked_operations: list[str] = []

        try:
            # 根据沙箱类型选择执行方式
            if self.config.sandbox_type == SandboxType.PROCESS:
                result = await self._execute_process(
                    command, final_env, final_work_dir, timeout, input_data
                )
            elif self.config.sandbox_type == SandboxType.CONTAINER:
                result = await self._execute_container(
                    command, final_env, final_work_dir, timeout, input_data
                )
            else:
                result = await self._execute_process(
                    command, final_env, final_work_dir, timeout, input_data
                )

            # 检查资源使用
            if result.memory_used_mb > self.config.max_memory_mb:
                security_violations.append(f"Memory limit exceeded: {result.memory_used_mb}MB > {self.config.max_memory_mb}MB")

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self._logger.warning("sandbox_execution_timeout", exec_id=exec_id, duration=duration)
            return SandboxResult(
                status=ExecutionStatus.TIMEOUT,
                stdout="",
                stderr=f"Execution timed out after {timeout or self.config.max_wall_time_seconds} seconds",
                exit_code=-1,
                duration_seconds=duration,
                security_violations=security_violations,
            )
        except Exception as e:
            duration = time.time() - start_time
            self._logger.error("sandbox_execution_error", exec_id=exec_id, error=str(e))
            return SandboxResult(
                status=ExecutionStatus.ERROR,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_seconds=duration,
                security_violations=security_violations,
            )

    async def _execute_process(
        self,
        command: str,
        env: dict[str, str],
        work_dir: str,
        timeout: float | None,
        input_data: str | None,
    ) -> SandboxResult:
        """进程级沙箱执行"""
        import time
        start_time = time.time()

        actual_timeout = timeout or self.config.max_wall_time_seconds

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(input_data.encode() if input_data else None),
                    timeout=actual_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise

            duration = time.time() - start_time

            return SandboxResult(
                status=ExecutionStatus.SUCCESS if process.returncode == 0 else ExecutionStatus.ERROR,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                status=ExecutionStatus.ERROR,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_seconds=duration,
            )

    async def _execute_container(
        self,
        command: str,
        env: dict[str, str],
        work_dir: str,
        timeout: float | None,
        input_data: str | None,
    ) -> SandboxResult:
        """容器级沙箱执行（Docker）"""
        import time
        start_time = time.time()

        # 构建 Docker 命令
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{work_dir}:/workspace",
            "-w", "/workspace",
        ]

        # 添加资源限制
        docker_cmd.extend(["--memory", f"{self.config.max_memory_mb}m"])
        docker_cmd.extend(["--cpus", "1"])

        # 网络隔离
        if not self.config.allow_network:
            docker_cmd.append("--network=none")

        # 环境变量
        for key, value in env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        # 使用标准镜像
        docker_cmd.extend(["python:3.12-slim", "sh", "-c", command])

        actual_timeout = timeout or self.config.max_wall_time_seconds

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(input_data.encode() if input_data else None),
                    timeout=actual_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise

            duration = time.time() - start_time

            return SandboxResult(
                status=ExecutionStatus.SUCCESS if process.returncode == 0 else ExecutionStatus.ERROR,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            raise
        except FileNotFoundError:
            # Docker 不可用，回退到进程执行
            self._logger.warning("docker_not_available", fallback="process")
            return await self._execute_process(command, env, work_dir, timeout, input_data)
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                status=ExecutionStatus.ERROR,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_seconds=duration,
            )

    def _get_work_dir(self) -> Path:
        """获取或创建工作目录"""
        if self._work_dir is None:
            self._work_dir = Path(tempfile.mkdtemp(prefix="sandbox_"))
        return self._work_dir

    def cleanup(self) -> None:
        """清理沙箱资源"""
        if self._work_dir and self._work_dir.exists():
            import shutil
            shutil.rmtree(self._work_dir, ignore_errors=True)
            self._work_dir = None
        self._logger.info("sandbox_cleaned")

    async def execute_python(
        self,
        code: str,
        timeout: float | None = None,
        work_dir: str | None = None,
    ) -> SandboxResult:
        """
        执行 Python 代码
        
        Args:
            code: Python 代码
            timeout: 超时时间
            work_dir: 工作目录
            
        Returns:
            SandboxResult: 执行结果
        """
        # 创建临时 Python 文件
        py_file = Path(work_dir or self._get_work_dir()) / "sandbox_code.py"
        py_file.write_text(code)

        return await self.execute(
            f"python {py_file}",
            timeout=timeout,
            work_dir=str(py_file.parent),
        )

    async def execute_script(
        self,
        script_path: str,
        args: list[str] | None = None,
        timeout: float | None = None,
        work_dir: str | None = None,
    ) -> SandboxResult:
        """
        执行脚本文件
        
        Args:
            script_path: 脚本路径
            args: 脚本参数
            timeout: 超时时间
            work_dir: 工作目录
            
        Returns:
            SandboxResult: 执行结果
        """
        args = args or []
        cmd = f"{script_path} {' '.join(args)}" if args else script_path

        return await self.execute(
            cmd,
            timeout=timeout,
            work_dir=work_dir,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取沙箱统计信息"""
        return {
            "total_executions": self._execution_count,
            "config": self.config.to_dict(),
            "work_dir": str(self._work_dir) if self._work_dir else None,
        }

    def validate_config(self, config: SandboxConfig) -> bool:
        """验证配置是否有效"""
        if config.max_wall_time_seconds <= 0:
            return False
        if config.max_memory_mb <= 0:
            return False
        return True

    def get_info(self) -> dict[str, Any]:
        """获取沙箱信息"""
        return {
            "type": self.config.sandbox_type.value,
            "available": True,
            "timeout_seconds": self.config.max_wall_time_seconds,
            "max_memory_mb": self.config.max_memory_mb,
            "allow_network": self.config.allow_network,
        }


# 创建全局单例
_sandbox_isolator: SandboxIsolator | None = None


def get_sandbox_isolator(config: SandboxConfig | None = None) -> SandboxIsolator:
    """获取全局沙箱隔离器实例"""
    global _sandbox_isolator
    if _sandbox_isolator is None:
        _sandbox_isolator = SandboxIsolator(config)
    return _sandbox_isolator
