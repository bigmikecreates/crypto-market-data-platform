from datetime import datetime

import typer

from crypto_market_data_platform.cli.ingestion_service import IngestionService
from crypto_market_data_platform.providers.bitfinex import BitfinexProvider
from crypto_market_data_platform.providers.fake import FakeProvider
from crypto_market_data_platform.providers.kucoin import KuCoinProvider

app = typer.Typer()

PROVIDERS: dict[str, type] = {
    "fake": FakeProvider,
    "bitfinex": BitfinexProvider,
    "kucoin": KuCoinProvider,
}


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
