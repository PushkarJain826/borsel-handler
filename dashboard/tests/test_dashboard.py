"""Tests for Phase 2 Dashboard: API client, chart builders, and UI helper functions."""

from datetime import date
import pandas as pd
import pytest
from unittest.mock import patch
import httpx

from dashboard.api_client import (
    ApiClientError,
    BackendUnavailableError,
    BorselApiClient,
    ResourceNotFoundError,
)
from dashboard.charts import create_price_line_chart, create_volume_bar_chart
from dashboard.styles import render_kpi, TERMINAL_CSS


def test_styles_and_kpi_renderer() -> None:
    """Verify that CSS and KPI renderers return non-empty styled HTML strings."""
    assert "stApp" in TERMINAL_CSS
    assert "#0b0f19" in TERMINAL_CSS

    kpi_html = render_kpi("Total Records", "1,240", "Sample description", subtext_type="success")
    assert "Total Records" in kpi_html
    assert "1,240" in kpi_html
    assert "kpi-subtext-success" in kpi_html


def test_chart_generation_line_and_candle() -> None:
    """Verify that Plotly figures are generated with expected traces and layouts."""
    sample_data = {
        "trading_date": pd.date_range("2026-01-01", periods=40, freq="D"),
        "open": [100.0 + i for i in range(40)],
        "high": [105.0 + i for i in range(40)],
        "low": [98.0 + i for i in range(40)],
        "close": [102.0 + i for i in range(40)],
        "volume": [1000000 + i * 1000 for i in range(40)],
    }
    df = pd.DataFrame(sample_data)

    # 1. Line chart
    fig_line = create_price_line_chart(df, symbol="RELIANCE.NS", chart_type="Line")
    assert fig_line is not None
    assert len(fig_line.data) >= 1
    assert fig_line.layout.paper_bgcolor == "#111827"

    # 2. Candlestick chart
    fig_candle = create_price_line_chart(df, symbol="RELIANCE.NS", chart_type="Candlestick")
    assert fig_candle is not None
    assert fig_candle.data[0].type == "candlestick"

    # 3. Volume bar chart
    fig_vol = create_volume_bar_chart(df, symbol="RELIANCE.NS")
    assert fig_vol is not None
    assert fig_vol.data[0].type == "bar"


def test_api_client_health_and_summary_live() -> None:
    """Verify BorselApiClient against running FastAPI backend."""
    client = BorselApiClient(base_url="http://localhost:8000")

    # 1. Health
    health = client.check_health()
    assert health["is_healthy"] is True
    assert health["status"] == "ok"

    # 2. Summary
    summary = client.get_summary()
    assert "total_records" in summary
    assert summary["total_records"] >= 1000
    assert len(summary["tracked_stocks"]) == 5

    # 3. Stocks list
    stocks = client.get_stocks()
    assert len(stocks) == 5
    symbols = {s["symbol"] for s in stocks}
    assert "RELIANCE.NS" in symbols
    assert "TCS.NS" in symbols

    # 4. Stock history
    history = client.get_stock_history("TCS.NS", limit=10)
    assert len(history) == 10
    assert history[0]["symbol"] == "TCS.NS"
    assert history[0]["data_source"] == "Yahoo Finance"

    # 5. Ingestion runs
    runs = client.get_ingestion_runs(limit=5)
    assert len(runs) > 0


def test_api_client_error_handling_and_resilience() -> None:
    """Verify error propagation and graceful degradation when backend fails."""
    # 1. 404 on unknown symbol
    client = BorselApiClient(base_url="http://localhost:8000")
    with pytest.raises(ResourceNotFoundError):
        client.get_stock_history("UNKNOWN_TICKER_DOES_NOT_EXIST")

    # 2. Complete backend offline / unreachable
    dead_client = BorselApiClient(base_url="http://localhost:59999", default_timeout=1.0)
    dead_health = dead_client.check_health()
    assert dead_health["is_healthy"] is False
    assert dead_health["status"] in ("offline", "error")

    with pytest.raises(BackendUnavailableError):
        dead_client.get_summary()
