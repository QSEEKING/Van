# Changelog

All notable changes to CoPaw Code will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-04-01

### Added
- **Core Agent Engine**: MainAgent with ReAct loop implementation
- **Agent Coordinator**: Multi-agent orchestration system
- **Sub Agents**: Explore, Plan, Verify, Review, Batch, Security agents
- **LLM Integration**: Anthropic Claude and OpenAI GPT support
- **Tool System**: File operations (read, write, edit, glob, grep)
- **Shell Execution**: Safe command execution with sandbox
- **Security Module**: SecurityMonitor, PermissionManager, SandboxIsolator
- **Storage Module**: SQLAlchemy async database support
- **Memory System**: Session memory and long-term memory
- **CLI Interface**: Interactive REPL with slash commands
- **Output Formatter**: Rich terminal output formatting

### Security
- Path traversal protection
- Command injection prevention
- File size limits
- Timeout enforcement
- Permission-based access control

### Testing
- 500 unit tests with 85% coverage
- Async test support with pytest-asyncio
- Coverage reporting with pytest-cov

## [0.0.1] - 2025-03-15

### Added
- Initial project structure
- Basic configuration system
- Core module skeleton