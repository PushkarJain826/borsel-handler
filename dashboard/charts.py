"""Plotly chart builders for Borsel Handler Terminal Dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def create_price_line_chart(df: pd.DataFrame, symbol: str, chart_type: str = "Line") -> go.Figure:
    """Create an interactive price chart (Line with area fill or Candlestick) for a stock.
    
    Expects df sorted ascending by trading_date with columns:
    ['trading_date', 'open', 'high', 'low', 'close', 'volume'].
    """
    fig = go.Figure()

    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=df["trading_date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
                increasing_line_color="#10b981",
                decreasing_line_color="#ef4444",
                increasing_fillcolor="#10b981",
                decreasing_fillcolor="#ef4444",
            )
        )
    else:
        # Sleek line chart with gradient fill
        fig.add_trace(
            go.Scatter(
                x=df["trading_date"],
                y=df["close"],
                mode="lines",
                name=f"{symbol} Close",
                line=dict(color="#0ea5e9", width=2.2),
                fill="tozeroy",
                fillcolor="rgba(14, 165, 233, 0.08)",
                hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Close:</b> ₹%{y:,.2f}<extra></extra>",
            )
        )

    # 50-day moving average if enough points exist
    if len(df) >= 30:
        ma20 = df["close"].rolling(window=20).mean()
        fig.add_trace(
            go.Scatter(
                x=df["trading_date"],
                y=ma20,
                mode="lines",
                name="20-day SMA",
                line=dict(color="#f59e0b", width=1.2, dash="dash"),
                hovertemplate="<b>20 SMA:</b> ₹%{y:,.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=40, r=20, t=35, b=20),
        height=380,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#9ca3af"),
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickformat="%b %Y",
            rangeslider=dict(visible=False),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="All"),
                ]),
                bgcolor="#1f2937",
                activecolor="#0ea5e9",
                font=dict(color="#e5e7eb", size=10),
            ),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickprefix="₹",
            tickformat=",.0f",
            side="right",
        ),
    )

    return fig


def create_volume_bar_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Create an interactive daily volume bar chart."""
    fig = go.Figure()

    # Determine up/down color for volume bars if open/close present
    if "open" in df.columns and "close" in df.columns:
        colors = [
            "rgba(16, 185, 129, 0.65)" if c >= o else "rgba(239, 68, 68, 0.65)"
            for o, c in zip(df["open"], df["close"])
        ]
    else:
        colors = ["rgba(56, 189, 248, 0.65)"] * len(df)

    fig.add_trace(
        go.Bar(
            x=df["trading_date"],
            y=df["volume"],
            name="Volume",
            marker_color=colors,
            hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Volume:</b> %{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=40, r=20, t=25, b=20),
        height=200,
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickformat="%b %Y",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickformat=",.2s",
            side="right",
        ),
    )

    return fig
