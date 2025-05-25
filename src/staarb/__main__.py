import click

from staarb.cli import backtest, dashboard


@click.group()
def cli():
    pass


cli.add_command(backtest.backtest)
cli.add_command(dashboard.dashboard)


if __name__ == "__main__":
    cli()
