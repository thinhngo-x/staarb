from datetime import UTC, datetime
from typing import Any

import click
import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html
from dash.dash_table import DataTable
from dash.dependencies import Input, Output

from staarb.persistence.backtest_storage import BacktestStorage

# Constants
WIN_RATE_THRESHOLD = 50  # Percentage threshold for good vs poor win rate


class BacktestDashboard:
    """Interactive dashboard for visualizing backtest results."""

    def __init__(self, storage: BacktestStorage):
        self.storage = storage
        self.app = dash.Dash(__name__)
        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self):
        """Setup the dashboard layout."""
        self.app.layout = html.Div(
            [
                html.H1(
                    "Statistical Arbitrage Backtest Dashboard",
                    style={"textAlign": "center", "marginBottom": "30px"},
                ),
                html.Div(
                    [
                        html.H3("Available Backtests"),
                        dcc.Dropdown(
                            id="backtest-dropdown",
                            options=[],
                            placeholder="Select a backtest to analyze",
                            style={"marginBottom": "20px"},
                        ),
                        html.Button(
                            "Refresh", id="refresh-button", n_clicks=0, style={"marginBottom": "20px"}
                        ),
                    ]
                ),
                html.Div(
                    id="dashboard-content",
                    children=[
                        html.P(
                            "Select a backtest to view results.",
                            style={"textAlign": "center", "fontSize": "18px", "marginTop": "50px"},
                        )
                    ],
                ),
            ]
        )

    def _setup_callbacks(self):
        """Setup dashboard callbacks."""

        @self.app.callback(Output("backtest-dropdown", "options"), [Input("refresh-button", "n_clicks")])
        def update_backtest_dropdown(_n_clicks):
            """Update the dropdown with available backtests."""
            try:
                backtests = self.storage.list_backtest_results()
                options = []
                for bt in backtests:
                    timestamp = datetime.fromisoformat(bt["timestamp"]).strftime("%Y-%m-%d %H:%M")
                    label = f"{bt['backtest_id']} ({', '.join(bt['symbols'])}) - {timestamp}"
                    options.append({"label": label, "value": bt["backtest_id"]})
            except (FileNotFoundError, OSError, ValueError) as e:
                # Use click for error output instead of logging
                click.echo(f"Error loading backtests: {e}", err=True)
                return []
            else:
                return options

        @self.app.callback(Output("dashboard-content", "children"), [Input("backtest-dropdown", "value")])
        def update_dashboard_content(selected_backtest_id):
            """Update dashboard content based on selected backtest."""
            if not selected_backtest_id:
                return html.P(
                    "Select a backtest to view results.",
                    style={"textAlign": "center", "fontSize": "18px", "marginTop": "50px"},
                )

            try:
                return self._create_backtest_analysis(selected_backtest_id)
            except (FileNotFoundError, KeyError, ValueError) as e:
                return html.Div(
                    [html.H3("Error Loading Backtest", style={"color": "red"}), html.P(f"Error: {e!s}")]
                )

    def _create_backtest_analysis(self, backtest_id: str) -> html.Div:
        """Create comprehensive analysis for a selected backtest."""
        try:
            data = self.storage.load_backtest_result(backtest_id)
            metadata = data["metadata"]
            summary = data["summary"]

            # Get positions DataFrame
            positions_df = self.storage.get_positions_dataframe(backtest_id)

            return html.Div(
                [
                    # Summary Cards
                    self._create_summary_cards(summary, metadata),
                    # PnL Chart
                    html.Hr(),
                    html.H3("Position PnL Analysis"),
                    dcc.Graph(id=f"pnl-chart-{backtest_id}", figure=self._create_pnl_chart(positions_df)),
                    # Position Distribution
                    html.Hr(),
                    html.H3("Position Distribution"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Graph(
                                        id=f"pnl-histogram-{backtest_id}",
                                        figure=self._create_pnl_histogram(positions_df),
                                    )
                                ],
                                style={"width": "48%", "display": "inline-block"},
                            ),
                            html.Div(
                                [
                                    dcc.Graph(
                                        id=f"symbol-analysis-{backtest_id}",
                                        figure=self._create_symbol_analysis(positions_df),
                                    )
                                ],
                                style={"width": "48%", "float": "right", "display": "inline-block"},
                            ),
                        ]
                    ),
                    # Detailed Positions Table
                    html.Hr(),
                    html.H3("Detailed Positions"),
                    self._create_positions_table(positions_df),
                    # Metadata
                    html.Hr(),
                    html.H3("Backtest Metadata"),
                    self._create_metadata_display(metadata, summary),
                ]
            )

        except (FileNotFoundError, KeyError, ValueError) as e:
            return html.Div(
                [html.H3("Error", style={"color": "red"}), html.P(f"Failed to load backtest data: {e!s}")]
            )

    def _create_summary_cards(self, summary: dict[str, Any], metadata: dict[str, Any]) -> html.Div:  # noqa: ARG002
        """Create summary cards showing key metrics."""
        total_pnl = summary.get("total_pnl", 0)
        total_trades = summary.get("total_trades", 0)
        win_rate = summary.get("win_rate", 0) * 100
        account_size = 1000

        return html.Div(
            [
                html.H3("Performance Summary"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.H4("Total PnL"),
                                html.P(
                                    f"${total_pnl:.2f}",
                                    style={
                                        "fontSize": "24px",
                                        "color": "green" if total_pnl >= 0 else "red",
                                        "fontWeight": "bold",
                                    },
                                ),
                            ],
                            className="summary-card",
                            style={
                                "border": "1px solid #ddd",
                                "padding": "20px",
                                "margin": "10px",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "width": "23%",
                                "display": "inline-block",
                            },
                        ),
                        html.Div(
                            [
                                html.H4("Return %"),
                                html.P(
                                    f"{(total_pnl / account_size) * 100:.2f}%",
                                    style={
                                        "fontSize": "24px",
                                        "color": "green" if total_pnl >= 0 else "red",
                                        "fontWeight": "bold",
                                    },
                                ),
                            ],
                            className="summary-card",
                            style={
                                "border": "1px solid #ddd",
                                "padding": "20px",
                                "margin": "10px",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "width": "23%",
                                "display": "inline-block",
                            },
                        ),
                        html.Div(
                            [
                                html.H4("Total Trades"),
                                html.P(f"{total_trades}", style={"fontSize": "24px", "fontWeight": "bold"}),
                            ],
                            className="summary-card",
                            style={
                                "border": "1px solid #ddd",
                                "padding": "20px",
                                "margin": "10px",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "width": "23%",
                                "display": "inline-block",
                            },
                        ),
                        html.Div(
                            [
                                html.H4("Win Rate"),
                                html.P(
                                    f"{win_rate:.1f}%",
                                    style={
                                        "fontSize": "24px",
                                        "fontWeight": "bold",
                                        "color": "green" if win_rate >= WIN_RATE_THRESHOLD else "orange",
                                    },
                                ),
                            ],
                            className="summary-card",
                            style={
                                "border": "1px solid #ddd",
                                "padding": "20px",
                                "margin": "10px",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "width": "23%",
                                "display": "inline-block",
                            },
                        ),
                    ]
                ),
            ]
        )

    def _create_pnl_chart(self, positions_df: pd.DataFrame) -> go.Figure:
        """Create PnL chart showing cumulative returns."""
        if positions_df.empty:
            return go.Figure().add_annotation(
                text="No position data available", xref="paper", yref="paper", x=0.5, y=0.5
            )

        # Filter out open positions (they shouldn't be in cumulative PnL)
        closed_positions = positions_df[positions_df["is_closed"]].copy()

        if closed_positions.empty:
            return go.Figure().add_annotation(
                text="No closed positions to display", xref="paper", yref="paper", x=0.5, y=0.5
            )

        # Sort positions chronologically by first transaction timestamp
        # Handle cases where first_timestamp might be None by putting them at the end
        closed_positions["sort_timestamp"] = closed_positions["first_timestamp"].fillna(float("inf"))
        closed_positions = closed_positions.sort_values("sort_timestamp")
        closed_positions["cumulative_pnl"] = closed_positions["pnl"].cumsum()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[datetime.fromtimestamp(ts // 1000, UTC) for ts in closed_positions["sort_timestamp"]],
                y=closed_positions["cumulative_pnl"],
                mode="lines+markers",
                name="Cumulative PnL",
                line={"color": "blue", "width": 2},
                marker={"size": 6},
                text=closed_positions["position_id"],  # Show position ID on hover
                hovertemplate="<b>Position:</b> %{text}<br><b>Cumulative PnL:</b> $%{y:.2f}<extra></extra>",
            )
        )

        fig.update_layout(
            title="Cumulative PnL Over Time (Chronological Order)",
            xaxis_title="Position Sequence",
            yaxis_title="Cumulative PnL ($)",
            hovermode="closest",
        )

        return fig

    def _create_pnl_histogram(self, positions_df: pd.DataFrame) -> go.Figure:
        """Create histogram of individual position PnLs."""
        if positions_df.empty:
            return go.Figure().add_annotation(
                text="No position data available", xref="paper", yref="paper", x=0.5, y=0.5
            )

        fig = px.histogram(
            positions_df,
            x="pnl",
            nbins=20,
            title="Distribution of Position PnL",
            labels={"pnl": "PnL ($)", "count": "Number of Positions"},
        )

        # Add vertical line at zero
        fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Breakeven")

        return fig

    def _create_symbol_analysis(self, positions_df: pd.DataFrame) -> go.Figure:
        """Create analysis by symbol."""
        if positions_df.empty:
            return go.Figure().add_annotation(
                text="No position data available", xref="paper", yref="paper", x=0.5, y=0.5
            )

        symbol_pnl = positions_df.groupby("symbol")["pnl"].sum().reset_index()

        fig = px.bar(
            symbol_pnl,
            x="symbol",
            y="pnl",
            title="PnL by Symbol",
            labels={"pnl": "Total PnL ($)", "symbol": "Symbol"},
        )

        # Color bars based on positive/negative PnL
        fig.update_traces(marker_color=["green" if pnl >= 0 else "red" for pnl in symbol_pnl["pnl"]])

        return fig

    def _create_positions_table(self, positions_df: pd.DataFrame):
        """Create detailed positions table."""
        if positions_df.empty:
            return html.P("No position data available.")

        # Format the DataFrame for display
        display_df = positions_df.copy()
        for col in ["entry_price", "exit_price", "pnl"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(4)

        return DataTable(  # type: ignore[operator]
            data=display_df.to_dict("records"),
            columns=[{"name": col, "id": col} for col in display_df.columns],
            style_cell={"textAlign": "left", "padding": "10px"},
            style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
            style_data_conditional=[
                {
                    "if": {"filter_query": "{pnl} > 0"},
                    "backgroundColor": "#d4edda",
                    "color": "black",
                },
                {
                    "if": {"filter_query": "{pnl} < 0"},
                    "backgroundColor": "#f8d7da",
                    "color": "black",
                },
            ],
            sort_action="native",
            filter_action="native",
            page_size=20,
        )

    def _create_metadata_display(self, metadata: dict[str, Any], summary: dict[str, Any]) -> html.Div:
        """Create metadata display."""
        return html.Div(
            [
                html.Div(
                    [
                        html.H4("Backtest Parameters"),
                        html.P(f"Backtest ID: {metadata.get('backtest_id', 'N/A')}"),
                        html.P(f"Timestamp: {metadata.get('timestamp', 'N/A')}"),
                        html.P(f"Portfolio: {metadata.get('portfolio_name', 'N/A')}"),
                        html.P(f"Account Size: ${metadata.get('account_size', 'N/A')}"),
                        html.P(f"Leverage: {metadata.get('leverage', 'N/A')}x"),
                        html.P(f"Symbols: {', '.join(metadata.get('symbols', []))}"),
                    ],
                    style={"width": "48%", "display": "inline-block", "verticalAlign": "top"},
                ),
                html.Div(
                    [
                        html.H4("Performance Metrics"),
                        html.P(f"Total PnL: ${summary.get('total_pnl', 0):.2f}"),
                        html.P(f"Total Trades: {summary.get('total_trades', 0)}"),
                        html.P(f"Winning Trades: {summary.get('winning_trades', 0)}"),
                        html.P(f"Losing Trades: {summary.get('losing_trades', 0)}"),
                        html.P(f"Win Rate: {summary.get('win_rate', 0) * 100:.1f}%"),
                    ],
                    style={
                        "width": "48%",
                        "float": "right",
                        "display": "inline-block",
                        "verticalAlign": "top",
                    },
                ),
            ]
        )

    def run(self, *, host: str = "127.0.0.1", port: int = 8050, debug: bool = True):
        """Run the dashboard server."""
        self.app.run(host=host, port=port, debug=debug)


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to run the dashboard on.")
@click.option("--port", default=8050, type=int, help="Port to run the dashboard on.")
@click.option("--storage-dir", default="backtest_results", help="Directory containing backtest results.")
@click.option("--debug/--no-debug", default=True, help="Run in debug mode.")
def dashboard(*, host: str, port: int, storage_dir: str, debug: bool):
    """Launch the backtest results dashboard."""
    click.echo(f"Starting dashboard on http://{host}:{port}")
    click.echo(f"Using storage directory: {storage_dir}")

    storage = BacktestStorage(storage_dir)

    # Check if there are any backtest results
    try:
        results = storage.list_backtest_results()
        if not results:
            click.echo("No backtest results found. Run some backtests first!")
            click.echo("Example: staarb backtest BTCUSDT ETHUSDT 2024-01-01 2024-02-01")
            return
        click.echo(f"Found {len(results)} backtest result(s)")
    except (OSError, ValueError) as e:
        click.echo(f"Error accessing storage: {e}")
        return

    dashboard_app = BacktestDashboard(storage)
    dashboard_app.run(host=host, port=port, debug=debug)
