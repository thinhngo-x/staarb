import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from staarb.portfolio.portfolio import Portfolio


class BacktestStorage:
    """Storage system for backtest results."""

    def __init__(self, storage_dir: str = "backtest_results"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save_backtest_result(
        self,
        backtest_id: str,
        portfolio: Portfolio,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save backtest results to storage."""
        timestamp = datetime.now(UTC)
        backtest_data = {
            "backtest_id": backtest_id,
            "timestamp": timestamp.isoformat(),
            "portfolio_name": portfolio.name,
            "account_size": portfolio.account_size,
            "leverage": portfolio.leverage,
            "symbols": [str(symbol) for symbol in portfolio.symbols],
            "metadata": metadata or {},
        }

        # Save portfolio data (create a clean copy without client reference)
        portfolio_file = self.storage_dir / f"{backtest_id}_portfolio.pkl"
        with portfolio_file.open("wb") as f:
            clean_portfolio = self._create_clean_portfolio_copy(portfolio)
            pickle.dump(clean_portfolio, f)

        # Save metadata as JSON
        metadata_file = self.storage_dir / f"{backtest_id}_metadata.json"
        with metadata_file.open("w") as f:
            json.dump(backtest_data, f, indent=2)

        # Create position summary
        position_summary = self._create_position_summary(portfolio)
        summary_file = self.storage_dir / f"{backtest_id}_summary.json"
        with summary_file.open("w") as f:
            json.dump(position_summary, f, indent=2)

        return backtest_id

    def load_backtest_result(self, backtest_id: str) -> dict[str, Any]:
        """Load backtest results from storage."""
        portfolio_file = self.storage_dir / f"{backtest_id}_portfolio.pkl"
        metadata_file = self.storage_dir / f"{backtest_id}_metadata.json"
        summary_file = self.storage_dir / f"{backtest_id}_summary.json"

        if not all(f.exists() for f in [portfolio_file, metadata_file, summary_file]):
            msg = f"Backtest data for {backtest_id} not found"
            raise FileNotFoundError(msg)

        with portfolio_file.open("rb") as pf:
            portfolio = pickle.load(pf)  # noqa: S301

        with metadata_file.open("r") as mf:
            metadata = json.load(mf)

        with summary_file.open("r") as sf:
            summary = json.load(sf)

        return {
            "portfolio": portfolio,
            "metadata": metadata,
            "summary": summary,
        }

    def list_backtest_results(self) -> list[dict[str, Any]]:
        """List all available backtest results."""
        results = []
        for metadata_file in self.storage_dir.glob("*_metadata.json"):
            with metadata_file.open("r") as f:
                metadata = json.load(f)
            results.append(metadata)

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results

    def delete_backtest_result(self, backtest_id: str) -> None:
        """Delete backtest results from storage."""
        files_to_delete = [
            self.storage_dir / f"{backtest_id}_portfolio.pkl",
            self.storage_dir / f"{backtest_id}_metadata.json",
            self.storage_dir / f"{backtest_id}_summary.json",
        ]

        for file_path in files_to_delete:
            if file_path.exists():
                file_path.unlink()

    def _create_position_summary(self, portfolio: Portfolio | dict[str, Any]) -> dict[str, Any]:
        """Create a summary of portfolio positions."""
        total_pnl = 0.0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0

        position_details = []

        # Handle both Portfolio object and dict formats
        if isinstance(portfolio, dict):
            closed_positions = portfolio.get("closed_positions", {})
            open_positions = portfolio.get("open_positions", {})
        else:
            closed_positions = portfolio.closed_positions
            open_positions = portfolio.open_positions

        # Process closed positions
        for symbol, positions in closed_positions.items():
            for position in positions:
                total_pnl += position.pnl
                total_trades += 1

                if position.pnl > 0:
                    winning_trades += 1
                elif position.pnl < 0:
                    losing_trades += 1

                position_details.append(
                    {
                        "symbol": str(symbol),
                        "size": position.size,
                        "entry_price": position.entry_price,
                        "exit_price": position.exit_price,
                        "pnl": position.pnl,
                        "is_closed": position.is_closed,
                        "transaction_count": len(position.transaction_history),
                    }
                )

        # Process open positions
        for symbol, position in open_positions.items():
            # Count open positions with transactions as trades too
            if len(position.transaction_history) > 0:
                total_trades += 1
                # Note: Open positions don't contribute to win/loss counts since they're not closed

            position_details.append(
                {
                    "symbol": str(symbol),
                    "size": position.size,
                    "entry_price": position.entry_price,
                    "exit_price": position.exit_price,
                    "pnl": position.pnl,
                    "is_closed": position.is_closed,
                    "transaction_count": len(position.transaction_history),
                }
            )

        return {
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0.0,
            "position_details": position_details,
        }

    def get_positions_dataframe(self, backtest_id: str) -> pd.DataFrame:
        """Get positions as a pandas DataFrame for analysis."""
        data = self.load_backtest_result(backtest_id)
        portfolio = data["portfolio"]

        positions_data = []

        # Handle both new (dict) and old (Portfolio object) formats
        if isinstance(portfolio, dict):
            closed_positions = portfolio.get("closed_positions", {})
            open_positions = portfolio.get("open_positions", {})
        else:
            closed_positions = portfolio.closed_positions
            open_positions = portfolio.open_positions

        # Process closed positions
        for symbol, positions in closed_positions.items():
            for i, position in enumerate(positions):
                # Get first transaction timestamp for chronological ordering
                first_timestamp = None
                if position.transaction_history:
                    first_tx = position.transaction_history[0]
                    first_timestamp = first_tx.transact_time

                positions_data.append(
                    {
                        "position_id": f"{symbol}_{i}",
                        "symbol": str(symbol),
                        "size": position.size,
                        "entry_price": position.entry_price,
                        "exit_price": position.exit_price,
                        "pnl": position.pnl,
                        "is_closed": position.is_closed,
                        "transaction_count": len(position.transaction_history),
                        "direction": "LONG" if position.size > 0 else "SHORT",
                        "first_timestamp": first_timestamp,
                    }
                )

        # Process open positions
        for symbol, position in open_positions.items():
            # Get first transaction timestamp for chronological ordering
            first_timestamp = None
            if position.transaction_history:
                first_tx = position.transaction_history[0]
                first_timestamp = first_tx.transact_time

            positions_data.append(
                {
                    "position_id": f"{symbol}_open",
                    "symbol": str(symbol),
                    "size": position.size,
                    "entry_price": position.entry_price,
                    "exit_price": position.exit_price,
                    "pnl": position.pnl,
                    "is_closed": position.is_closed,
                    "transaction_count": len(position.transaction_history),
                    "direction": "LONG" if position.size > 0 else "SHORT",
                    "first_timestamp": first_timestamp,
                }
            )

        return pd.DataFrame(positions_data)

    def _create_clean_portfolio_copy(self, portfolio: Portfolio) -> dict[str, Any]:
        """Create a clean copy of portfolio data without unpicklable references."""
        return {
            "name": portfolio.name,
            "account_size": portfolio.account_size,
            "leverage": portfolio.leverage,
            "symbols": portfolio.symbols,
            "open_positions": portfolio.open_positions,
            "closed_positions": portfolio.closed_positions,
        }
