"""API router for Phase 1 Demo Market Data Pipeline."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from borsel.db.session import get_session
from borsel.models.demo import DemoDailyPrice, DemoImportRun
from borsel.schemas.demo import (
    DemoImportRunResponse,
    DemoRefreshResponse,
    DemoStockPriceItem,
    DemoSummaryResponse,
    StockSummaryItem,
)
from borsel.services.demo_ingestion import (
    DATA_PROVIDER,
    TRACKED_SYMBOLS,
    ingest_demo_market_data,
)

router = APIRouter(prefix="/api/demo", tags=["Demo Market Data"])


@router.get(
    "/stocks",
    response_model=list[StockSummaryItem],
    summary="List tracked stocks and summary statistics",
)
async def list_tracked_stocks(
    session: AsyncSession = Depends(get_session),
) -> list[StockSummaryItem]:
    """Return status and latest observation summary for all tracked demo stocks."""
    results: list[StockSummaryItem] = []

    for sym in TRACKED_SYMBOLS:
        # Aggregate statistics for symbol
        agg_stmt = select(
            func.count(DemoDailyPrice.id),
            func.min(DemoDailyPrice.trading_date),
            func.max(DemoDailyPrice.trading_date),
        ).where(DemoDailyPrice.symbol == sym)

        agg_res = await session.execute(agg_stmt)
        count, first_d, last_d = agg_res.one()

        latest_close: Optional[float] = None
        latest_vol: Optional[int] = None

        if count > 0 and last_d is not None:
            latest_stmt = (
                select(DemoDailyPrice.close, DemoDailyPrice.volume)
                .where(
                    DemoDailyPrice.symbol == sym,
                    DemoDailyPrice.trading_date == last_d,
                )
                .limit(1)
            )
            latest_res = await session.execute(latest_stmt)
            latest_row = latest_res.first()
            if latest_row:
                latest_close = float(latest_row[0])
                latest_vol = int(latest_row[1])

        results.append(
            StockSummaryItem(
                symbol=sym,
                record_count=count or 0,
                first_date=first_d,
                last_date=last_d,
                latest_close=latest_close,
                latest_volume=latest_vol,
                data_source=DATA_PROVIDER,
            )
        )

    return results


@router.get(
    "/stocks/{symbol}",
    response_model=list[DemoStockPriceItem],
    summary="Get daily price history for a symbol",
)
async def get_stock_prices(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
) -> list[DemoStockPriceItem]:
    """Retrieve historical OHLCV observations for a specific stock."""
    sym_upper = symbol.strip().upper()

    stmt = select(DemoDailyPrice).where(DemoDailyPrice.symbol == sym_upper)

    if order == "desc":
        stmt = stmt.order_by(DemoDailyPrice.trading_date.desc())
    else:
        stmt = stmt.order_by(DemoDailyPrice.trading_date.asc())

    stmt = stmt.limit(limit)
    res = await session.execute(stmt)
    records = res.scalars().all()

    if not records:
        # Check if symbol exists at all
        check_stmt = select(func.count(DemoDailyPrice.id)).where(
            DemoDailyPrice.symbol == sym_upper
        )
        total = (await session.execute(check_stmt)).scalar_one()
        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for symbol '{sym_upper}'. Try refreshing market data first.",
            )

    return [DemoStockPriceItem.model_validate(r) for r in records]


@router.get(
    "/summary",
    response_model=DemoSummaryResponse,
    summary="Get overall demo pipeline summary",
)
async def get_demo_summary(
    session: AsyncSession = Depends(get_session),
) -> DemoSummaryResponse:
    """Return top-level database metrics, date ranges, and latest import run."""
    # Total records and global date range
    agg_stmt = select(
        func.count(DemoDailyPrice.id),
        func.min(DemoDailyPrice.trading_date),
        func.max(DemoDailyPrice.trading_date),
    )
    total_records, earliest_d, latest_d = (await session.execute(agg_stmt)).one()

    # Latest import run
    run_stmt = (
        select(DemoImportRun)
        .order_by(DemoImportRun.started_at.desc())
        .limit(1)
    )
    latest_run = (await session.execute(run_stmt)).scalar_one_or_none()

    # Stocks summary
    stocks_summary = await list_tracked_stocks(session)

    return DemoSummaryResponse(
        total_records=total_records or 0,
        tracked_stocks=TRACKED_SYMBOLS,
        earliest_date=earliest_d,
        latest_date=latest_d,
        stocks_summary=stocks_summary,
        latest_run=(
            DemoImportRunResponse.model_validate(latest_run) if latest_run else None
        ),
    )


@router.post(
    "/refresh",
    response_model=DemoRefreshResponse,
    summary="Trigger historical market data refresh from Yahoo Finance",
)
async def refresh_market_data(
    period: str = Query(
        default="1y",
        description="Historical period to fetch (e.g. 1mo, 3mo, 6mo, 1y, 2y)",
    ),
    session: AsyncSession = Depends(get_session),
) -> DemoRefreshResponse:
    """Fetch historical daily data for all tracked stocks from Yahoo Finance and save to PostgreSQL."""
    run, details = await ingest_demo_market_data(session, period=period)

    return DemoRefreshResponse(
        message=f"Market data refresh completed with status '{run.status}'",
        run_id=run.id,
        status=run.status,
        provider=DATA_PROVIDER,
        records_processed=run.records_processed,
        records_failed=run.records_failed,
        symbols_refreshed=list(details.keys()),
        details=details,
    )


@router.get(
    "/ingestion-runs",
    response_model=list[DemoImportRunResponse],
    summary="List recent ingestion execution runs",
)
async def list_ingestion_runs(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[DemoImportRunResponse]:
    """Retrieve history of market data ingestion runs and their statuses."""
    stmt = (
        select(DemoImportRun)
        .order_by(DemoImportRun.started_at.desc())
        .limit(limit)
    )
    runs = (await session.execute(stmt)).scalars().all()
    return [DemoImportRunResponse.model_validate(r) for r in runs]
