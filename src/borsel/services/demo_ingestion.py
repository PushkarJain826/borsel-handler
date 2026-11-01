"""Market data ingestion service using Yahoo Finance (Phase 1 MVP).

Clearly identifies Yahoo Finance as the external provider.
Uses thread-offloading to avoid blocking the async event loop.
Validates records and performs idempotent upserts into PostgreSQL.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import yfinance as yf

from borsel.models.demo import DemoDailyPrice, DemoImportRun

logger = logging.getLogger(__name__)

DATA_PROVIDER = "Yahoo Finance"
TRACKED_SYMBOLS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
]


def _fetch_symbol_history_sync(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Synchronous worker to fetch data from Yahoo Finance via yfinance."""
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, auto_adjust=False)
    return df


def _validate_and_normalize_row(
    symbol: str,
    ts: pd.Timestamp,
    row: pd.Series,
    now_utc: datetime,
) -> Optional[dict]:
    """Validate OHLCV data. Returns normalized dictionary or None if invalid."""
    try:
        trading_date = ts.date()
        open_val = float(row.get("Open", 0.0))
        high_val = float(row.get("High", 0.0))
        low_val = float(row.get("Low", 0.0))
        close_val = float(row.get("Close", 0.0))

        adj_close_raw = row.get("Adj Close", None)
        adj_close = float(adj_close_raw) if pd.notna(adj_close_raw) else None

        volume_raw = row.get("Volume", 0)
        volume = int(volume_raw) if pd.notna(volume_raw) else 0

        # Basic financial validity checks
        if any(pd.isna(x) for x in (open_val, high_val, low_val, close_val)):
            return None
        if open_val <= 0 or high_val <= 0 or low_val <= 0 or close_val <= 0:
            return None
        if high_val < low_val:
            return None
        if volume < 0:
            return None

        return {
            "id": uuid.uuid4(),
            "symbol": symbol,
            "trading_date": trading_date,
            "open": round(open_val, 4),
            "high": round(high_val, 4),
            "low": round(low_val, 4),
            "close": round(close_val, 4),
            "adjusted_close": round(adj_close, 4) if adj_close is not None else None,
            "volume": volume,
            "data_source": DATA_PROVIDER,
            "fetched_at": now_utc,
        }
    except Exception as exc:
        logger.debug("Validation error for %s on %s: %s", symbol, ts, exc)
        return None


async def ingest_demo_market_data(
    session: AsyncSession,
    symbols: Optional[list[str]] = None,
    period: str = "1y",
) -> tuple[DemoImportRun, dict[str, int]]:
    """Fetch and ingest historical market data for tracked stocks from Yahoo Finance.

    Uses thread offloading for synchronous yfinance API calls.
    Performs conflict-safe upsert on (symbol, trading_date, data_source).
    Logs execution results in ingestion.demo_import_runs.
    """
    target_symbols = symbols or TRACKED_SYMBOLS
    now_utc = datetime.now(timezone.utc)

    # 1. Initialize import run record
    import_run = DemoImportRun(
        started_at=now_utc,
        status="RUNNING",
        provider=DATA_PROVIDER,
        records_processed=0,
        records_failed=0,
    )
    session.add(import_run)
    await session.commit()
    await session.refresh(import_run)

    total_processed = 0
    total_failed = 0
    symbol_counts: dict[str, int] = {}
    errors: list[str] = []

    for symbol in target_symbols:
        try:
            # 2. Non-blocking thread offload for network fetch
            df = await asyncio.to_thread(_fetch_symbol_history_sync, symbol, period)

            if df is None or df.empty:
                logger.warning("No data returned by %s for symbol %s", DATA_PROVIDER, symbol)
                total_failed += 1
                errors.append(f"{symbol}: No data returned")
                symbol_counts[symbol] = 0
                continue

            records_to_upsert: list[dict] = []
            for ts, row in df.iterrows():
                record = _validate_and_normalize_row(symbol, ts, row, now_utc)
                if record:
                    records_to_upsert.append(record)
                else:
                    total_failed += 1

            if records_to_upsert:
                # 3. Idempotent upsert via ON CONFLICT DO UPDATE
                stmt = pg_insert(DemoDailyPrice).values(records_to_upsert)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trading_date", "data_source"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "adjusted_close": stmt.excluded.adjusted_close,
                        "volume": stmt.excluded.volume,
                        "fetched_at": stmt.excluded.fetched_at,
                    },
                )
                await session.execute(stmt)
                await session.commit()

                symbol_counts[symbol] = len(records_to_upsert)
                total_processed += len(records_to_upsert)
            else:
                symbol_counts[symbol] = 0
                total_failed += len(df)
                errors.append(f"{symbol}: All records failed validation")

        except Exception as exc:
            logger.error("Failed ingesting %s from %s: %s", symbol, DATA_PROVIDER, exc)
            total_failed += 1
            errors.append(f"{symbol}: {str(exc)}")
            symbol_counts[symbol] = 0

    # 4. Finalize run status
    completed_utc = datetime.now(timezone.utc)
    import_run.completed_at = completed_utc
    import_run.records_processed = total_processed
    import_run.records_failed = total_failed

    if total_processed > 0 and not errors:
        import_run.status = "COMPLETED"
    elif total_processed > 0 and errors:
        import_run.status = "PARTIAL"
        import_run.error_message = "; ".join(errors)
    else:
        import_run.status = "FAILED"
        import_run.error_message = "; ".join(errors) if errors else "No records processed"

    await session.commit()
    await session.refresh(import_run)

    return import_run, symbol_counts
