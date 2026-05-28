from datetime import datetime
from typing import Any

import typer

import uvicorn

from crypto_market_data_platform.ingestion import FundingRateService, OhlcvService
from crypto_market_data_platform.utils.parquet_viewer import run_inspect
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.providers.bitfinex import BitfinexProvider
from crypto_market_data_platform.providers.bitstamp import BitstampProvider
from crypto_market_data_platform.providers.bybit import BybitProvider
from crypto_market_data_platform.providers.fake import FakeProvider
from crypto_market_data_platform.providers.kucoin import KuCoinProvider
from crypto_market_data_platform.providers.mexc import MexcProvider
from crypto_market_data_platform.query import DuckDBQueryService
from crypto_market_data_platform.server import create_app

app = typer.Typer(name="cmpd")

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "bitstamp": BitstampProvider,
    "kucoin": KuCoinProvider,
    "bybit": BybitProvider,
    "mexc": MexcProvider,
}

_query_service = DuckDBQueryService()


# ── fetch ────────────────────────────────────────────────────────


@app.command()
def fetch(
    market_data_type: str = typer.Option(
        "ohlcv",
        "--mdt",
        help="Market data type: ohlcv or funding-rate",
    ),
    symbol: str = typer.Option("BTC/USDT", "--symbol", help="Trading pair symbol"),
    timeframe: str = typer.Option(
        "1h", "--timeframe", help="Candle timeframe (ohlcv only)"
    ),
    start: datetime = typer.Option(
        ...,
        "--start",
        formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"],
        help="Start time (ISO-8601)",
    ),
    end: datetime = typer.Option(
        ...,
        "--end",
        formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"],
        help="End time (ISO-8601)",
    ),
    provider: str = typer.Option(
        "fake",
        "--provider",
        help="Data provider to use (ohlcv only)",
    ),
    output: str = typer.Option(
        "data",
        "--output",
        help="Base output directory",
    ),
    merge_strategy: str = typer.Option(
        "auto",
        "--merge-strategy",
        help="Row merge strategy: auto (default), memory, or duckdb",
    ),
) -> None:
    if market_data_type not in ("ohlcv", "funding-rate"):
        typer.echo(
            f"Invalid market data type '{market_data_type}'. Use ohlcv or funding-rate.",
            err=True,
        )
        raise typer.Exit(code=1)

    if merge_strategy not in ("auto", "memory", "duckdb"):
        typer.echo(
            f"Invalid merge strategy '{merge_strategy}'. Use auto, memory, or duckdb.",
            err=True,
        )
        raise typer.Exit(code=1)

    if market_data_type == "funding-rate":
        p = FakeProvider()
        rates = p.fetch_funding_rates(symbol=symbol, start=start, end=end)
        fr_svc = FundingRateService()
        count = fr_svc.ingest(rates, base_path=output, merge_strategy=merge_strategy)
        typer.echo(f"Wrote {count} funding rate(s) to {output}/")
        return

    provider_cls = PROVIDERS.get(provider)
    if provider_cls is None:
        available = ", ".join(PROVIDERS)
        typer.echo(f"Unknown provider '{provider}'. Available: {available}", err=True)
        raise typer.Exit(code=1)

    ohlcv_svc = OhlcvService(provider=provider_cls())
    count = ohlcv_svc.ingest(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        base_path=output,
        merge_strategy=merge_strategy,
    )
    typer.echo(f"Wrote {count} candle(s) to {output}/")


# ── datasets ─────────────────────────────────────────────────────


@app.command()
def datasets(
    path: str = typer.Option("data", "--path", help="Base data directory"),
) -> None:
    """List available datasets grouped by type."""
    svc = DuckDBQueryService()
    all_datasets = svc.list_datasets(path)
    if not all_datasets:
        typer.echo(f"No parquet files found under {path}/")
        raise typer.Exit(code=1)

    summary = svc.get_summary(path)
    for row in summary:
        parts = [
            f"  {row['type']:15s} {row['exchange']:10s} {row['symbol']:12s}",
        ]
        if row["timeframe"]:
            parts.append(f"{row['timeframe']:6s}")
        parts.append(f"files={row['files']}  rows={row['rows']}")
        typer.echo("".join(parts))


# ── query group ──────────────────────────────────────────────────

_query_app = typer.Typer(name="query")
app.add_typer(_query_app)


@_query_app.command("ohlcv")
def query_ohlcv(
    path: str = typer.Option("data", "--path", help="Base data directory"),
    exchange: str = typer.Option(None, "--exchange", help="Filter by exchange"),
    symbol: str = typer.Option(None, "--symbol", help="Filter by symbol"),
    timeframe: str = typer.Option(None, "--timeframe", help="Filter by timeframe"),
    start: str = typer.Option(None, "--start", help="Start timestamp (inclusive)"),
    end: str = typer.Option(None, "--end", help="End timestamp (exclusive)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max rows"),
) -> None:
    """Query candle data."""
    svc = DuckDBQueryService()
    rows = svc.get_candles(
        base_path=path,
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )
    _print_rows(rows)


@_query_app.command("funding-rate")
def query_funding_rate(
    path: str = typer.Option("data", "--path", help="Base data directory"),
    exchange: str = typer.Option(None, "--exchange", help="Filter by exchange"),
    symbol: str = typer.Option(None, "--symbol", help="Filter by symbol"),
    start: str = typer.Option(None, "--start", help="Start timestamp (inclusive)"),
    end: str = typer.Option(None, "--end", help="End timestamp (exclusive)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max rows"),
) -> None:
    """Query funding rate data."""
    svc = DuckDBQueryService()
    rows = svc.get_funding_rates(
        base_path=path,
        exchange=exchange,
        symbol=symbol,
        start=start,
        end=end,
        limit=limit,
    )
    _print_rows(rows)


@_query_app.command("sql")
def query_sql(
    sql: str = typer.Argument(..., help="SQL query"),
    path: str = typer.Option("data", "--path", help="Base data directory"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max rows"),
) -> None:
    """Run raw SQL via DuckDB read_parquet."""
    svc = DuckDBQueryService()
    rows = svc.raw_sql(sql, base_path=path)
    if limit:
        rows = rows[:limit]
    _print_rows(rows)


# ── serve ─────────────────────────────────────────────────────────


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    path: str = typer.Option("data", "--path", help="Base data directory"),
) -> None:
    """Start the FastAPI REST server."""
    from crypto_market_data_platform.server.config import ServerConfig

    config = ServerConfig(host=host, port=port, base_path=path)
    uvicorn.run(
        create_app(config),
        host=host,
        port=port,
    )


# ── inspect ──────────────────────────────────────────────────────


@app.command()
def inspect(
    path: str = typer.Option(
        ..., "--path", help="Path to a .parquet file or dataset directory"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max rows in sample"),
    start: str = typer.Option(
        None, "--start", help="Start of timestamp range (ISO-8601), inclusive"
    ),
    end: str = typer.Option(
        None, "--end", help="End of timestamp range (ISO-8601), exclusive"
    ),
    stats_flag: bool = typer.Option(False, "--stats", help="Show column statistics"),
    verbose_flag: bool = typer.Option(
        False, "--verbose", help="Show full Parquet metadata"
    ),
) -> None:
    """Inspect a parquet file or dataset directory."""
    try:
        output = run_inspect(
            path_str=path,
            limit=limit,
            start=start,
            end=end,
            show_stats=stats_flag,
            show_verbose=verbose_flag,
        )
        typer.echo(output)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# ── helpers ──────────────────────────────────────────────────────


def _print_rows(rows: list[Any]) -> None:
    if not rows:
        typer.echo("(no results)")
        return
    if isinstance(rows[0], (Candle, FundingRate)):
        columns = [f.name for f in rows[0].__dataclass_fields__.values()]
        data = {c: [getattr(r, c) for r in rows] for c in columns}
    else:
        columns = list(rows[0].keys())
        data = {c: [r[c] for r in rows] for c in columns}

    typer.echo("  " + " | ".join(columns))
    typer.echo("  " + "-" * len(" | ".join(columns)))
    for i in range(len(rows)):
        vals = [str(data[c][i]) for c in columns]
        typer.echo("  " + " | ".join(vals))
    typer.echo(f"  ({len(rows)} row(s))")
