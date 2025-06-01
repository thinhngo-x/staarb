# Staarb

Staarb is a modular Python framework for statistical arbitrage trading, supporting backtesting, live trading, and paper trading. It is designed for flexibility and extensibility, making it easy to implement and test new trading strategies.

## Features
- Modular architecture for strategies, data, and trading clients
- Backtesting and paper/live trading modes
- Event-driven core with extensible event bus
- Example strategies and utilities

## Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd staarb
   ```
2. Install dependencies:
   
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

## Usage

- Run a backtest:
  ```bash
  python -m staarb.cli.backtest --help
  ```
- Live or paper trading:
  ```bash
  python -m staarb.cli.live_trade --help
  python -m staarb.cli.paper_trade --help
  ```

## Common Tasks

**With uv (recommended):**
- **Run tests:** `uv run pytest`
- **Lint code:** `uv run ruff check src tests`
- **Format code:** `uv run ruff format src tests`
- **Type check:** `uv run mypy src`

**With Make (alternative):**
- **Run tests:** `make test`
- **Lint code:** `make lint`
- **Format code:** `make format`
- **Type check:** `make typecheck`
- **Run all checks:** `make all`
- **See all options:** `make help`

**With pip/standard tools:**
- **Run tests:** `pytest`
- **Lint code:** `ruff check src tests`
- **Format code:** `ruff format src tests`
- **Type check:** `mypy src`

## Project Structure

- `src/staarb/` - Main package
- `tests/` - Unit and integration tests

## License

MIT License
