# kutx2spotify development commands

set shell := ["bash", "-cu"]

venv := env_var("HOME") / "venvs/kutx2spotify"
python := venv / "bin/python"
pip := venv / "bin/pip"

# Show available commands
default:
    @just --list

# Install dependencies
dev:
    python3 -m venv {{venv}}
    {{pip}} install -e ".[dev]"

# Format code
format:
    {{venv}}/bin/ruff format src tests
    {{venv}}/bin/ruff check --fix src tests

# Lint code
lint:
    {{venv}}/bin/ruff check src tests

# Type check
typecheck:
    {{venv}}/bin/mypy src

# Run tests
test *args:
    {{venv}}/bin/pytest {{args}}

# Run tests in watch mode
test-watch:
    {{venv}}/bin/pytest --watch

# Run tests with coverage
coverage:
    {{venv}}/bin/pytest --cov=src --cov-report=term-missing --cov-report=html

# Run all checks (format, lint, typecheck, test)
check-all: format lint typecheck test

# Clean build artifacts
clean:
    rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install git hooks
hooks:
    @echo '#!/bin/bash' > .git/hooks/pre-commit
    @echo 'just format && just lint && just typecheck' >> .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit
    @echo '#!/bin/bash' > .git/hooks/pre-push
    @echo 'just check-all' >> .git/hooks/pre-push
    @chmod +x .git/hooks/pre-push
    @echo "Git hooks installed"
