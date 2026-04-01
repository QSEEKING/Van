# Contributing to CoPaw Code

Thank you for your interest in contributing to CoPaw Code! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/copaw-code.git`
3. Create a branch: `git checkout -b feature/your-feature`

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip or poetry for dependency management
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/copaw-team/copaw-code.git
cd copaw-code

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks (optional)
pre-commit install
```

### Environment Variables

```bash
# Required for LLM providers
export ANTHROPIC_API_KEY=sk-ant-xxx
export OPENAI_API_KEY=sk-xxx

# Optional
export COPAW_DEBUG=true
export COPAW_LOG_LEVEL=DEBUG
```

## Coding Standards

### Code Style

We use the following tools for code quality:

- **Black**: Code formatting (line-length: 100)
- **isort**: Import sorting (profile: black)
- **Ruff**: Linting (select: E, F, I, N, W)
- **mypy**: Type checking

### Running Linters

```bash
# Format code
black .
isort .

# Check linting
ruff check .

# Type checking
mypy .
```

### Code Guidelines

1. **Type Hints**: Use type hints for all function signatures
2. **Docstrings**: Use Google-style docstrings for public functions
3. **Async**: Use async/await for I/O operations
4. **Error Handling**: Use structured logging and proper exception handling
5. **Testing**: Write tests for all new functionality

### Example Docstring

```python
def process_file(file_path: str, encoding: str = "utf-8") -> str:
    """Process a file and return its content.
    
    Args:
        file_path: Path to the file to process.
        encoding: File encoding, defaults to utf-8.
    
    Returns:
        The file content as a string.
    
    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
```

## Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_tools.py -v

# Run specific test
pytest tests/unit/test_tools.py::TestFileReader::test_read_file -v
```

### Test Coverage Requirements

- Minimum coverage: 85%
- All new code must have tests
- Critical paths require 100% coverage

### Writing Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_dependency():
    """Create a mock dependency."""
    return Mock()

class TestMyFeature:
    """Test MyFeature class."""
    
    def test_basic_functionality(self, mock_dependency):
        """Test basic functionality."""
        result = my_function(mock_dependency)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async functionality."""
        result = await my_async_function()
        assert result.success
```

## Pull Request Process

1. **Create a Branch**: Use descriptive names like `feature/add-x` or `fix/issue-y`
2. **Make Changes**: Follow coding standards
3. **Write Tests**: Ensure adequate test coverage
4. **Run Tests**: All tests must pass
5. **Update Docs**: Update documentation if needed
6. **Submit PR**: Fill out the PR template completely

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Coverage meets requirements (≥85%)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No breaking changes (or documented)

## Issue Reporting

### Bug Reports

Include:
1. Description of the bug
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment details (Python version, OS)
6. Relevant logs or screenshots

### Feature Requests

Include:
1. Description of the feature
2. Use case / motivation
3. Proposed solution (optional)
4. Alternatives considered (optional)

---

Thank you for contributing! 🎉