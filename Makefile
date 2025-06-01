# Makefile for Staarb development tasks
# Use uv if available, fallback to standard tools

# Check if uv is available
HAS_UV := $(shell command -v uv 2> /dev/null)

ifdef HAS_UV
    RUN_PREFIX := uv run
else
    RUN_PREFIX :=
endif

.PHONY: help install test lint format typecheck clean all

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
ifdef HAS_UV
	uv venv .venv
	uv pip install -e .
else
	python -m venv .venv
	.venv/bin/pip install -e .
endif

test:  ## Run tests
	$(RUN_PREFIX) pytest

lint:  ## Lint code
	$(RUN_PREFIX) ruff check src tests

format:  ## Format code
	$(RUN_PREFIX) ruff format src tests

typecheck:  ## Run type checking
	$(RUN_PREFIX) mypy src

clean:  ## Clean cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

all: lint typecheck test  ## Run all checks
