# Security Policy

## Supported Versions

We actively support the following versions of CoPaw Code with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x: (pre-release)  |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities.

2. **Email us** at security@copaw.dev with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

3. **Response Time**:
   - We will acknowledge receipt within 48 hours
   - We will provide an initial assessment within 7 days
   - We will work on a fix and coordinate disclosure

### What to Include

- **Vulnerability Type**: Code injection, path traversal, etc.
- **Affected Component**: File operations, shell execution, LLM interface, etc.
- **Attack Vector**: How the vulnerability can be exploited
- **Impact**: What an attacker can achieve
- **Proof of Concept**: Steps or code to demonstrate the vulnerability
- **Environment**: Python version, OS, etc.

## Security Features

CoPaw Code implements multiple security layers:

### 1. Path Traversal Protection
- All file operations are validated against allowed directories
- Symlink resolution prevents directory escape
- Hidden files are blocked by default

### 2. Command Injection Prevention
- Shell commands are filtered for dangerous patterns
- Known dangerous commands are blocked (rm -rf /, sudo, etc.)
- Timeout enforcement prevents runaway processes

### 3. Input Validation
- All inputs are sanitized before processing
- File sizes are limited
- Request rates are controlled

### 4. Sandboxed Execution
- Commands run in isolated environments
- Resource limits (CPU, memory, time)
- Network access is controlled

### 5. Permission System
- Role-based access control (USER, DEVELOPER, ADMIN)
- Granular permissions (READ, WRITE, EXECUTE, ADMIN)
- Operation-level authorization

## Security Best Practices

When using CoPaw Code:

1. **API Keys**: Never commit API keys to version control
   ```bash
   # Use environment variables
   export ANTHROPIC_API_KEY=sk-ant-xxx
   export OPENAI_API_KEY=sk-xxx
   ```

2. **Working Directory**: Always set a restricted working directory
   ```python
   agent = MainAgent(working_dir="/safe/directory")
   ```

3. **Permissions**: Use minimal required permissions
   ```python
   manager.grant(Role.USER, Permission.READ)  # Read-only
   ```

4. **Sandboxing**: Enable sandboxing for untrusted inputs
   ```python
   isolator = SandboxIsolator(config)
   await isolator.execute(command)
   ```

5. **Logging**: Enable security logging
   ```yaml
   security:
     audit_logging: true
     strict_mode: true
   ```

## Security Audit

We regularly perform security audits:

- **Dependency scanning**: Using `safety` and `pip-audit`
- **Code scanning**: Using `bandit` and `semgrep`
- **Container scanning**: Using `trivy` for Docker images

Run security checks:
```bash
# Check dependencies
pip install safety
safety check --full-report

# Code scanning
pip install bandit
bandit -r . -ll

# Container scanning
trivy image copaw-code:latest
```

## Disclosure Policy

We follow responsible disclosure:

1. Vulnerability is reported privately
2. We investigate and confirm the issue
3. We develop and test a fix
4. We release the fix and update CHANGELOG
5. We publicly disclose after users have had time to update

## Contact

- Security Email: security@copaw.dev
- General Issues: https://github.com/copaw-team/copaw-code/issues

Thank you for helping keep CoPaw Code secure!