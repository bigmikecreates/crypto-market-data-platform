from datetime import datetime
from typing import Any

import typer

import uvicorn

from crypto_market_data_platform.cli.funding_ingestion_service import FundingIngestionService
from crypto_market_data_platform.cli.ingestion_service import IngestionService
from crypto_market_data_platform.models.candle import Candle
from crypto_market_data_platform.models.funding_rate import FundingRate
from crypto_market_data_platform.providers.bitfinex import BitfinexProvider
from crypto_market_data_platform.providers.fake import FakeProvider
from crypto_market_data_platform.providers.kucoin import KuCoinProvider
from crypto_market_data_platform.query import DuckDBQueryService
from crypto_market_data_platform.server import create_app

app = typer.Typer(name="cmpd")

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "kucoin": KuCoinProvider,
}

_query_service = DuckDBQueryService()


# ── fetch (existing) ────────────────────────────────────────────


@app.command()
def fetch(
    symbol: str = typer.Option("BTC/USDT", "--symbol", help="Trading pair symbol"),
    timeframe: str = typer.Option("1h", "--timeframe", help="Candle timeframe"),
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
        help="Data provider to use",
    ),
    output: str = typer.Option(
        "data",
        "--output",
        help="Base output directory",
    ),
) -> None:
    provider_cls = PROVIDERS.get(provider)
    if provider_cls is None:
        available = ", ".join(PROVIDERS)
        typer.echo(f"Unknown provider '{provider}'. Available: {available}", err=True)
        raise typer.Exit(code=1)

    svc = IngestionService(provider=provider_cls())
    count = svc.ingest(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        base_path=output,
    )
    typer.echo(f"Wrote {count} candle(s) to {output}/")


# ── fetch-funding (existing) ─────────────────────────────────────


@app.command()
def fetch_funding(
    symbol: str = typer.Option("BTC/USDT", "--symbol", help="Trading pair symbol"),
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
    output: str = typer.Option(
        "data",
        "--output",
        help="Base output directory",
    ),
) -> None:
    provider = FakeProvider()
    rates = provider.fetch_funding_rates(
        symbol=symbol,
        start=start,
        end=end,
    )
    svc = FundingIngestionService()
    count = svc.ingest(rates, base_path=output)
    typer.echo(f"Wrote {count} funding rate(s) to {output}/")


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


# ── candles ──────────────────────────────────────────────────────

_candles_app = typer.Typer(name="candles")
app.add_typer(_candles_app)


@_candles_app.command("get")
def candles_get(
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
        base_path=path, exchange=exchange, symbol=symbol,
        timeframe=timeframe, start=start, end=end, limit=limit,
    )
    _print_rows(rows)


# ── funding ─────────────────────────────────────────────────────

_funding_app = typer.Typer(name="funding")
app.add_typer(_funding_app)


@_funding_app.command("get")
def funding_get(
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
        base_path=path, exchange=exchange, symbol=symbol,
        start=start, end=end, limit=limit,
    )
    _print_rows(rows)


# ── query (raw SQL, escape hatch) ────────────────────────────────


@app.command()
def query(
    sql: str = typer.Option(..., "--sql", help="SQL query"),
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
