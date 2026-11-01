"""Tests for Phase 1 Demo Market Data Pipeline (Yahoo Finance -> PostgreSQL -> FastAPI)."""

from datetime import date, datetime, timezone
from unittest.mock import patch
import uuid

import httpx
import pandas as pd
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from borsel.core.config import settings
from borsel.db.session import get_session
from borsel.main import app
from borsel.models.demo import DemoDailyPrice, DemoImportRun
from borsel.services.demo_ingestion import (
    DATA_PROVIDER,
    TRACKED_SYMBOLS,
    _validate_and_normalize_row,
    ingest_demo_market_data,
)

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
async_session_factory = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.mark.asyncio
async def test_demo_tables_exist() -> None:
    """Verify demo tables exist in market and ingestion schemas."""
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_name IN ('demo_daily_prices', 'demo_import_runs')"
            )
        )
        found = {(r[0], r[1]) for r in result.fetchall()}
        assert ("market", "demo_daily_prices") in found
        assert ("ingestion", "demo_import_runs") in found


@pytest.mark.asyncio
async def test_ohlcv_validation_logic() -> None:
    """Verify that _validate_and_normalize_row rejects invalid financial data."""
    now = datetime.now(timezone.utc)
    ts = pd.Timestamp("2026-01-15")

    # Valid row
    valid_row = pd.Series({"Open": 100.0, "High": 105.0, "Low": 98.0, "Close": 102.0, "Volume": 5000})
    res = _validate_and_normalize_row("TEST.NS", ts, valid_row, now)
    assert res is not None
    assert res["symbol"] == "TEST.NS"
    assert res["trading_date"] == date(2026, 1, 15)
    assert res["data_source"] == DATA_PROVIDER

    # Inverted High < Low
    inv_row = pd.Series({"Open": 100.0, "High": 95.0, "Low": 98.0, "Close": 96.0, "Volume": 5000})
    assert _validate_and_normalize_row("TEST.NS", ts, inv_row, now) is None

    # Negative price
    neg_row = pd.Series({"Open": -10.0, "High": 10.0, "Low": -15.0, "Close": 5.0, "Volume": 5000})
    assert _validate_and_normalize_row("TEST.NS", ts, neg_row, now) is None

    # Negative volume
    neg_vol = pd.Series({"Open": 100.0, "High": 105.0, "Low": 98.0, "Close": 102.0, "Volume": -100})
    assert _validate_and_normalize_row("TEST.NS", ts, neg_vol, now) is None


@pytest.mark.asyncio
async def test_duplicate_handling_upsert() -> None:
    """Verify that multiple ingestion runs on same date range perform idempotent upserts."""
    async with async_session_factory() as session:
        # Ingest for single symbol with 5d period
        run1, counts1 = await ingest_demo_market_data(session, symbols=["INFY.NS"], period="5d")
        assert run1.status in ("COMPLETED", "PARTIAL")

        count_stmt = select(DemoDailyPrice).where(DemoDailyPrice.symbol == "INFY.NS")
        records_after_1 = (await session.execute(count_stmt)).scalars().all()
        initial_count = len(records_after_1)
        assert initial_count > 0

        # Run second time for same symbol and period
        run2, counts2 = await ingest_demo_market_data(session, symbols=["INFY.NS"], period="5d")
        assert run2.status in ("COMPLETED", "PARTIAL")

        records_after_2 = (await session.execute(count_stmt)).scalars().all()
        # Count must remain exactly the same due to upsert
        assert len(records_after_2) == initial_count


@pytest.mark.asyncio
async def test_provider_failure_handling_no_fabrication() -> None:
    """Verify graceful handling when data provider fails; never fabricates data."""
    async with async_session_factory() as session:
        # Mock yfinance helper to simulate network/provider exception
        with patch("borsel.services.demo_ingestion._fetch_symbol_history_sync", side_effect=RuntimeError("Yahoo Finance API unreachable")):
            run, counts = await ingest_demo_market_data(
                session, symbols=["RELIANCE.NS"], period="5d"
            )

            assert run.status == "FAILED"
            assert run.records_processed == 0
            assert run.records_failed > 0
            assert "Yahoo Finance API unreachable" in (run.error_message or "")
            assert counts.get("RELIANCE.NS") == 0


@pytest.mark.asyncio
async def test_api_endpoints_via_httpx() -> None:
    """Verify API endpoints using httpx AsyncClient."""
    async def override_get_session():
        async with async_session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health check
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # 2. Stocks list
            resp = await client.get("/api/demo/stocks")
            assert resp.status_code == 200
            stocks = resp.json()
            assert len(stocks) == 5
            symbols = [s["symbol"] for s in stocks]
            assert set(symbols) == set(TRACKED_SYMBOLS)
            for s in stocks:
                assert s["data_source"] == "Yahoo Finance"

            # 3. Stock specific prices
            resp = await client.get("/api/demo/stocks/RELIANCE.NS?limit=10")
            assert resp.status_code == 200
            prices = resp.json()
            assert len(prices) > 0
            assert prices[0]["symbol"] == "RELIANCE.NS"
            assert "close" in prices[0]
            assert "open" in prices[0]
            assert prices[0]["data_source"] == "Yahoo Finance"

            # 4. Unknown stock 404
            resp = await client.get("/api/demo/stocks/UNKNOWN_STOCK_XYZ")
            assert resp.status_code == 404

            # 5. Pipeline summary
            resp = await client.get("/api/demo/summary")
            assert resp.status_code == 200
            summary = resp.json()
            assert summary["total_records"] >= 1000
            assert len(summary["tracked_stocks"]) == 5
            assert summary["latest_run"] is not None

            # 6. Ingestion runs
            resp = await client.get("/api/demo/ingestion-runs")
            assert resp.status_code == 200
            runs = resp.json()
            assert len(runs) > 0
            assert runs[0]["provider"] == "Yahoo Finance"
    finally:
        app.dependency_overrides.clear()
