import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from crmd_platform.ingestion import OHLCVService
from crmd_platform.providers import PROVIDERS
from crmd_platform.providers.base import OHLCVProvider
from crmd_platform.query import QueryService
from crmd_platform.server.dependencies import (
    get_base_path,
    get_query_service,
    get_storage_backend,
)
from crmd_platform.storage.backend import StorageBackend
from crmd_platform.utils.last_fetch import mark as mark_last_fetch

LOG = logging.getLogger(__name__)

router = APIRouter(tags=["fetch"])


class FetchRequest(BaseModel):
    data_type: str = Field(..., pattern=r"^(candles|funding-rates)$")
    provider: str
    symbol: str
    timeframe: str | None = None
    start: str
    end: str | None = None


class FetchResponse(BaseModel):
    count: int
    data_type: str
    provider: str
    symbol: str
    timeframe: str | None = None


def _parse_start_end(start: str, end: str | None) -> tuple[datetime, datetime]:
    formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
    parsed_start: datetime | None = None
    for fmt in formats:
        try:
            parsed_start = datetime.strptime(start, fmt)
            break
        except ValueError:
            continue
    if parsed_start is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid start format '{start}'. Use ISO-8601 (e.g. 2024-01-01 or 2024-01-01T00:00:00).",
        )

    if end is not None:
        parsed_end: datetime | None = None
        for fmt in formats:
            try:
                parsed_end = datetime.strptime(end, fmt)
                break
            except ValueError:
                continue
        if parsed_end is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid end format '{end}'. Use ISO-8601 (e.g. 2024-06-01 or 2024-06-01T00:00:00).",
            )
    else:
        parsed_end = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    if parsed_start >= parsed_end:
        raise HTTPException(
            status_code=400,
            detail="Start must be before end.",
        )

    return parsed_start, parsed_end


@router.post("/fetch", response_model=FetchResponse)
def handle_fetch(
    req: FetchRequest,
    base_path: str = Depends(get_base_path),
    qs: QueryService = Depends(get_query_service),
    backend: StorageBackend = Depends(get_storage_backend),
) -> FetchResponse:
    if req.data_type == "funding-rates":
        raise HTTPException(
            status_code=400,
            detail="Real funding rate providers are not yet implemented. "
            "Use the CLI with --mdt funding-rate for testing.",
        )

    if req.data_type == "candles" and not req.timeframe:
        raise HTTPException(
            status_code=400,
            detail="timeframe is required for candles.",
        )

    provider_cls = PROVIDERS.get(req.provider)
    if provider_cls is None:
        available = ", ".join(sorted(PROVIDERS))
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{req.provider}'. Available: {available}.",
        )

    if not issubclass(provider_cls, OHLCVProvider):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{req.provider}' does not support OHLCV data.",
        )

    start_dt, end_dt = _parse_start_end(req.start, req.end)

    # Pre-fetch validation: check stored coverage so we don't call the external
    # API when the requested start is already known to be unavailable.
    if req.data_type == "candles" and req.timeframe:
        earliest = qs.get_candles(
            base_path=base_path,
            exchange=req.provider,
            symbol=req.symbol,
            timeframe=req.timeframe,
            limit=1,
            order="ASC",
        )
        if earliest:
            first_ts = earliest[0].timestamp
            start_date = req.start[:10]
            first_date = first_ts[:10]
            if first_date > start_date:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot fetch candles for this start date. "
                        f"Requested start: {start_date}. "
                        f"Earliest available candle: {first_ts}."
                    ),
                )

    svc = OHLCVService(provider=provider_cls())
    try:
        count = svc.ingest(
            symbol=req.symbol,
            timeframe=req.timeframe,  # type: ignore[arg-type]
            start=start_dt,
            end=end_dt,
            base_path=base_path,
            merge_strategy="auto",
            backend=backend,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    mark_last_fetch(base_path)
    LOG.info(
        "Fetched %d candle(s) for %s/%s/%s",
        count,
        req.provider,
        req.symbol,
        req.timeframe,
    )

    return FetchResponse(
        count=count,
        data_type=req.data_type,
        provider=req.provider,
        symbol=req.symbol,
        timeframe=req.timeframe,
    )
