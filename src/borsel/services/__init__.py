"""Services package."""

from borsel.services.demo_ingestion import (
    DATA_PROVIDER,
    TRACKED_SYMBOLS,
    ingest_demo_market_data,
)

__all__ = [
    "DATA_PROVIDER",
    "TRACKED_SYMBOLS",
    "ingest_demo_market_data",
]
