import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import typer

import uvicorn

from crmd_platform.ingestion import FundingRateService, OHLCVService
from crmd_platform.utils.parquet_viewer import run_inspect
from crmd_platform.models.candle import Candle
from crmd_platform.models.funding_rate import FundingRate
from crmd_platform.providers.bitfinex import BitfinexProvider
from crmd_platform.providers.bitstamp import BitstampProvider
from crmd_platform.providers.bybit import BybitProvider
from crmd_platform.providers.fake import FakeProvider
from crmd_platform.providers.kucoin import KuCoinProvider
from crmd_platform.providers.mexc import MexcProvider
from crmd_platform.query import DuckDBQueryService
from crmd_platform.server import create_app

app = typer.Typer(name="crmd")

# Maps exchange-standard timeframe strings to their exact duration.
# Used by --since-last to advance the start past the last stored candle.
_TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "1w": timedelta(weeks=1),
}

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "bitstamp": BitstampProvider,
    "kucoin": KuCoinProvider,
    "bybit": BybitProvider,
    "mexc": MexcProvider,
}

# ── fetch ────────────────────────────────────────────────────────


@app.command()
def fetch(
    market_data_type: str = typer.Option(
        ...,
        "--mdt",
        help="Market data type: ohlcv or funding-rate",
    ),
    symbol: List[str] = typer.Option(
        ..., "--symbol", help="Trading pair symbol (repeat for multiple symbols)"
    ),
    timeframe: str = typer.Option(
        ..., "--timeframe", help="Candle timeframe (ohlcv only)"
    ),
    start: Optional[datetime] = typer.Option(
        None,
        "--start",
        formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"],
        help="Start time (ISO-8601). Omit when using --since-last.",
    ),
    end: Optional[datetime] = typer.Option(
        None,
        "--end",
        formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"],
        help="End time (ISO-8601). Defaults to now when using --since-last or --follow.",
    ),
    provider: str = typer.Option(
        ...,
        "--provider",
        help="Data provider to use (ohlcv only)",
    ),
    output: str = typer.Option(
        "data",
        "--output",
        help="Base output directory or az:// URI",
    ),
    merge_strategy: str = typer.Option(
        "auto",
        "--merge-strategy",
        help="Row merge strategy: auto (default), memory, or duckdb",
    ),
    workers: int = typer.Option(
        4,
        "--workers",
        help="Number of concurrent symbol fetches (ohlcv only)",
        min=1,
        max=32,
    ),
    since_last: bool = typer.Option(
        False,
        "--since-last",
        help="Auto-detect start from the last stored candle for each symbol. "
        "Replaces --start. Combine with --follow for continuous ingestion.",
    ),
    follow: Optional[int] = typer.Option(
        None,
        "--follow",
        help="After each fetch, sleep N seconds then fetch again. "
        "Use with --since-last to keep data continuously current.",
        min=1,
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

    if since_last and start is not None:
        typer.echo("--since-last and --start are mutually exclusive.", err=True)
        raise typer.Exit(code=1)

    if not since_last and start is None:
        typer.echo("Either --start or --since-last is required.", err=True)
        raise typer.Exit(code=1)

    if market_data_type == "funding-rate":
        if since_last or follow:
            typer.echo(
                "--since-last and --follow are not yet supported for funding-rate.",
                err=True,
            )
            raise typer.Exit(code=1)
        fr_svc = FundingRateService(provider=FakeProvider())
        effective_end = end or datetime.now(tz=timezone.utc).replace(tzinfo=None)
        for sym in symbol:
            count = fr_svc.ingest(
                symbol=sym,
                start=start,  # type: ignore[arg-type]
                end=effective_end,
                base_path=output,
                merge_strategy=merge_strategy,
            )
            typer.echo(f"Wrote {count} funding rate(s) for {sym} to {output}/")
        return

    provider_cls = PROVIDERS.get(provider)
    if provider_cls is None:
        available = ", ".join(PROVIDERS)
        typer.echo(f"Unknown provider '{provider}'. Available: {available}", err=True)
        raise typer.Exit(code=1)

    while True:
        effective_end = end or datetime.now(tz=timezone.utc).replace(tzinfo=None)

        # Resolve start: either explicit --start or auto-detected from stored data.
        if since_last:
            if timeframe not in _TIMEFRAME_DELTAS:
                typer.echo(
                    f"--since-last requires a known timeframe. "
                    f"Got {timeframe!r}; supported: {', '.join(_TIMEFRAME_DELTAS)}",
                    err=True,
                )
                raise typer.Exit(code=1)
            delta = _TIMEFRAME_DELTAS[timeframe]
            svc_q = DuckDBQueryService()
            resolved_starts: dict[str, datetime] = {}
            for sym in symbol:
                last = svc_q.get_candles(
                    base_path=output,
                    exchange=provider,  # scope to this provider's exchange only
                    symbol=sym,
                    timeframe=timeframe,
                    limit=1,
                    order="DESC",
                )
                if last:
                    # Advance one interval past the last stored candle so it is not
                    # re-fetched on every --follow cycle.
                    resolved_starts[sym] = (
                        datetime.fromisoformat(last[0].timestamp) + delta
                    )
                elif start is not None:
                    resolved_starts[sym] = start
                else:
                    typer.echo(
                        f"No existing data for {provider}/{sym}/{timeframe} and --start not provided. "
                        "Run with --start once to seed the dataset.",
                        err=True,
                    )
                    raise typer.Exit(code=1)
        else:
            resolved_starts = {sym: start for sym in symbol}  # type: ignore[assignment]

        def _fetch_one(sym: str) -> tuple[str, int]:
            svc = OHLCVService(provider=provider_cls())
            n = svc.ingest(
                symbol=sym,
                timeframe=timeframe,
                start=resolved_starts[sym],
                end=effective_end,
                base_path=output,
                merge_strategy=merge_strategy,
            )
            return sym, n

        effective_workers = min(workers, len(symbol))
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
            futures = {pool.submit(_fetch_one, sym): sym for sym in symbol}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    _, count = future.result()
                    typer.echo(f"Wrote {count} candle(s) for {sym} to {output}/")
                except Exception as e:
                    typer.echo(f"Error fetching {sym}: {e}", err=True)
                    errors.append(sym)

        if errors:
            if follow is None:
                raise typer.Exit(code=1)
            # In follow mode, log and continue — one transient provider error should
            # not kill continuous ingestion for all other symbols.
            typer.echo(
                f"[warn] {len(errors)} symbol(s) failed this cycle and will retry: "
                + ", ".join(errors),
                err=True,
            )

        if follow is None:
            break

        typer.echo(f"Sleeping {follow}s before next fetch...")
        time.sleep(follow)


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
    """Run raw SQL via DuckDB read_parquet (SELECT/WITH only)."""
    from crmd_platform.server.routers.query import (
        _FIRST_KEYWORD,
        _ALLOWED_KEYWORDS,
        has_multiple_statements,
        _STRIP_COMMENTS,
    )

    stripped = _STRIP_COMMENTS.sub("", sql).strip()
    m = _FIRST_KEYWORD.match(stripped)
    if not m or m.group(1).lower() not in _ALLOWED_KEYWORDS:
        raise typer.Exit("Only SELECT (or WITH … SELECT) statements are permitted.")
    if has_multiple_statements(stripped):
        raise typer.Exit("Multiple SQL statements are not permitted.")

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
    path: str = typer.Option("data", "--path", help="Base data directory or az:// URI"),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="CRMD_API_KEY",
        help="Require X-API-Key header on all data endpoints. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"',
    ),
    cors_origins: str = typer.Option(
        "http://localhost:3000,http://127.0.0.1:3000",
        "--cors-origins",
        envvar="CRMD_CORS_ORIGINS",
        help="Comma-separated list of allowed CORS origins.",
    ),
) -> None:
    """Start the FastAPI REST server."""
    from crmd_platform.server.config import ServerConfig

    config = ServerConfig(
        host=host,
        port=port,
        base_path=path,
        api_key=api_key,
        cors_origins=[o.strip() for o in cors_origins.split(",") if o.strip()],
    )
    uvicorn.run(create_app(config), host=host, port=port)


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
