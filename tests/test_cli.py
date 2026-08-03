"""Smoke tests del CLI (sin BD necesaria)."""

from typer.testing import CliRunner

from stonks.cli import app

runner = CliRunner()


def test_help_exit_0():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "stonks" in result.output.lower()


def test_subcommands_visibles():
    result = runner.invoke(app, ["--help"])
    for sub in (
        "macro",
        "equity",
        "crypto",
        "forex",
        "fund",
        "commodity",
        "deriv",
        "intraday",
    ):
        assert sub in result.output.lower()


def test_macro_help():
    result = runner.invoke(app, ["macro", "--help"])
    assert result.exit_code == 0


def test_equity_help():
    result = runner.invoke(app, ["equity", "--help"])
    assert result.exit_code == 0


def test_crypto_help():
    result = runner.invoke(app, ["crypto", "--help"])
    assert result.exit_code == 0


def test_deriv_help():
    result = runner.invoke(app, ["deriv", "--help"])
    assert result.exit_code == 0
    assert "vol-fetch" in result.output
    assert "futures-fetch" in result.output


def test_intraday_help():
    result = runner.invoke(app, ["intraday", "--help"])
    assert result.exit_code == 0
    assert "fetch" in result.output
    assert "cleanup" in result.output
    assert "partitions" in result.output
