.PHONY: install test lint format clean build docs coverage help

# Default target
help:
	@echo "CoPaw Code - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install dependencies"
	@echo "  test        Run all tests"
	@echo "  coverage    Run tests with coverage report"
	@echo "  lint        Run linting checks"
	@echo "  format      Format code with black and isort"
	@echo "  typecheck   Run type checking with mypy"
	@echo "  clean       Clean build artifacts"
	@echo "  build       Build distribution packages"
	@echo "  docs        Generate documentation"
	@echo "  all         Run all checks (lint, test, coverage)"

# Installation
install:
	pip install -e ".[dev]"
	pip install pre-commit
	pre-commit install

# Testing
test:
	pytest tests/ -v --tb=short

coverage:
	pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Code Quality
lint:
	ruff check .
	pytest tests/ --collect-only -q

format:
	black .
	isort .

typecheck:
	mypy --ignore-missing-imports .

# Build
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

# Documentation
docs:
	@echo "Documentation generation coming soon"

# All checks
all: format lint test coverage
	@echo "All checks passed!"