"""Demo models for Phase 1 MVP market data pipeline.

Includes demo_daily_prices in market schema and demo_import_runs in ingestion schema.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from borsel.db.base import Base


class DemoDailyPrice(Base):
    """Daily historical OHLCV price observation for demo market pipeline."""

    __tablename__ = "demo_daily_prices"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trading_date",
            "data_source",
            name="uq_demo_daily_prices_sym_date_src",
        ),
        CheckConstraint("high >= low", name="ck_demo_daily_prices_high_low"),
        CheckConstraint("volume >= 0", name="ck_demo_daily_prices_volume_nonneg"),
        Index("ix_demo_daily_prices_symbol_date", "symbol", "trading_date"),
        Index("ix_demo_daily_prices_trading_date", "trading_date"),
        {"schema": "market"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    adjusted_close: Mapped[Optional[float]] = mapped_column(
        Numeric(20, 4), nullable=True
    )
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class DemoImportRun(Base):
    """Ingestion execution run tracking for demo market data."""

    __tablename__ = "demo_import_runs"
    __table_args__ = (
        Index("ix_demo_import_runs_started_at", "started_at"),
        Index("ix_demo_import_runs_status", "status"),
        {"schema": "ingestion"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
