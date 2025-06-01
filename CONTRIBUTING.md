# Contributing to Staarb

Thank you for your interest in contributing! We welcome pull requests, bug reports, and feature suggestions.

## Getting Started

1. **Fork the repository** and create your branch from `main`.
2. **Set up your environment:**
   
   **With uv (recommended):**
   ```bash
   uv venv .venv
   source .venv/bin/activate
   uv pip install -e .
   ```
   
   **With pip:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```
3. **Write clear, concise code** and include tests for new features or bug fixes.
4. **Use these commands for common development tasks:**
   
   **With uv (recommended):**
   - Run tests: `uv run pytest`
   - Lint code: `uv run ruff check src tests`
   - Format code: `uv run ruff format src tests`
   - Type check: `uv run mypy src`
   
   **With Make (alternative):**
   - Run tests: `make test`
   - Lint code: `make lint`
   - Format code: `make format`
   - Type check: `make typecheck`
   - Run all checks: `make all`
   
   **With pip/standard tools:**
   - Run tests: `pytest`
   - Lint code: `ruff check src tests`
   - Format code: `ruff format src tests`
   - Type check: `mypy src`
5. **Open a pull request** with a clear description of your changes.

## Code Style
- Follow [PEP8](https://www.python.org/dev/peps/pep-0008/) guidelines.
- Use type hints where appropriate.
- Write docstrings for public modules, classes, and functions.

## Reporting Issues
- Use the GitHub Issues tracker.
- Provide as much detail as possible (steps to reproduce, expected/actual behavior, logs).

## Community
- Be respectful and constructive in all interactions.

Thank you for helping make Staarb better!
