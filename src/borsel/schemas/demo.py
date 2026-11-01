"""Pydantic schemas for Demo Market Data Pipeline (Phase 1 MVP)."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DemoStockPriceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: Optional[float] = None
    volume: int
    data_source: str
    fetched_at: datetime


class StockSummaryItem(BaseModel):
    symbol: str
    record_count: int
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    latest_close: Optional[float] = None
    latest_volume: Optional[int] = None
    data_source: str = "Yahoo Finance"


class DemoImportRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    provider: str
    records_processed: int
    records_failed: int
    error_message: Optional[str] = None


class DemoSummaryResponse(BaseModel):
    total_records: int
    tracked_stocks: list[str]
    earliest_date: Optional[date] = None
    latest_date: Optional[date] = None
    stocks_summary: list[StockSummaryItem]
    latest_run: Optional[DemoImportRunResponse] = None


class DemoRefreshResponse(BaseModel):
    message: str
    run_id: UUID
    status: str
    provider: str
    records_processed: int
    records_failed: int
    symbols_refreshed: list[str]
    details: dict[str, int] = Field(default_factory=dict)
