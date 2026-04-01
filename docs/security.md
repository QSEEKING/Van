# Security Architecture

## Overview

CoPaw Code implements a multi-layer security architecture to ensure safe operation when processing user requests and executing tools.

## Security Layers

### 1. SecurityMonitor

The `SecurityMonitor` class validates all operations before execution:

- **Path validation**: Prevents path traversal attacks
- **Command filtering**: Blocks dangerous shell commands
- **Size limits**: Enforces file size restrictions
- **Rate limiting**: Prevents abuse

```python
from security import get_security_monitor, SecurityLevel

monitor = get_security_monitor()
result = monitor.check_operation("read", "/app/sensitive.txt")

if result.level >= SecurityLevel.HIGH:
    print(f"Warning: {result.message}")
```

### 2. PermissionManager

The `PermissionManager` implements role-based access control:

- **Permission flags**: READ, WRITE, EXECUTE, ADMIN
- **Roles**: USER, DEVELOPER, ADMIN
- **Rules**: Granular permission rules

```python
from security import PermissionManager, Permission, Role

manager = PermissionManager()
manager.grant(Role.USER, Permission.READ | Permission.WRITE)

if manager.check(user, Permission.EXECUTE):
    # Allow execution
```

### 3. SandboxIsolator

The `SandboxIsolator` provides isolated execution environment:

- **Timeout enforcement**: Prevents runaway processes
- **Resource limits**: CPU, memory, file descriptors
- **Network isolation**: Optional network blocking
- **Filesystem isolation**: Restricted write access

```python
from security import SandboxIsolator, SandboxConfig

config = SandboxConfig(
    max_wall_time_seconds=30,
    max_cpu_seconds=10,
    allow_network=False
)

isolator = SandboxIsolator(config)
result = await isolator.execute("git status")
```

## Security Levels

| Level | Description | Action |
|-------|-------------|--------|
| PASS | Operation allowed | Execute immediately |
| LOW | Minor concern | Log and execute |
| MEDIUM | Moderate concern | Log with details |
| HIGH | Significant concern | Warn user |
| CRITICAL | Dangerous operation | Block execution |

## Protected Operations

### File Operations
- Path traversal prevention
- Symlink attack mitigation
- Hidden file restrictions
- Size limit enforcement

### Shell Commands
- Command injection prevention
- Dangerous command blocking (`rm -rf /`, `sudo`, etc.)
- Timeout enforcement
- Output sanitization

### Network Access
- URL validation
- Host allowlist/blocklist
- Request timeout
- Response size limit

## Best Practices

1. **Always validate inputs** before processing
2. **Use sandbox** for shell command execution
3. **Check permissions** before sensitive operations
4. **Log security events** for auditing
5. **Handle errors gracefully** without exposing internals

## Configuration

Security settings in `config/default.yaml`:

```yaml
security:
  default_sandbox_level: 1   # TIMEOUT
  command_timeout: 30
  max_file_size_mb: 10
  require_approval_for_write: false
```

## Reporting Issues

If you discover a security vulnerability, please report it privately to the maintainers. Do not create public issues for security vulnerabilities.