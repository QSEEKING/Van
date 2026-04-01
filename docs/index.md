# CoPaw Code Documentation

## Overview

CoPaw Code is an AI-powered coding assistant similar to Claude Code, built with a modular architecture for extensibility and security.

## Architecture

### Core Components

1. **Agent Engine** (`core/agent/`)
   - MainAgent: ReAct loop implementation
   - Coordinator: Multi-agent orchestration
   - SubAgents: Explore, Plan, Verify, Review, Security

2. **LLM Interface** (`core/llm/`)
   - Abstract base class for providers
   - Anthropic Claude implementation
   - OpenAI GPT implementation
   - Provider factory/adapter

3. **Tool System** (`tools/`)
   - File operations: read, write, edit
   - Search: glob, grep
   - Shell: safe command execution

4. **Security Module** (`security/`)
   - SecurityMonitor: Operation validation
   - PermissionManager: Access control
   - SandboxIsolator: Execution sandbox

5. **Storage Module** (`storage/`)
   - SQLAlchemy async models
   - Session and message storage
   - Memory and tool call tracking

6. **CLI Interface** (`cli/`)
   - Interactive REPL
   - Slash commands
   - Rich output formatting

## Configuration

See `config/default.yaml` for default settings.

Key configuration areas:
- LLM provider and model settings
- Database connection
- Security levels and timeouts
- Memory and token budgets

## API Reference

### MainAgent

```python
from core.agent.main_agent import MainAgent
from core.llm.adapter import create_llm_provider

llm = create_llm_provider()
agent = MainAgent(llm=llm, working_dir="/path/to/project")

# Process a request
result = await agent.process("List all Python files")
```

### Tool Usage

```python
from tools import register_default_tools, ToolRegistry

registry = ToolRegistry.get_instance()
register_default_tools()

# Execute a tool
tool = registry.get("read_file")
result = await tool.execute({"file_path": "/app/main.py"})
```

### Security Check

```python
from security import get_security_monitor

monitor = get_security_monitor()
passed, result = monitor.check_operation("read", "/app/file.py")
```

## Development

See `CONTRIBUTING.md` for development guidelines.

## Security

See `docs/security.md` for security architecture and best practices.

## License

MIT License - see `LICENSE` file.