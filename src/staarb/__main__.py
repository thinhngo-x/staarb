import click

from staarb.cli import backtest


@click.group()
def cli():
    pass


cli.add_command(backtest.backtest)


if __name__ == "__main__":
    cli()
