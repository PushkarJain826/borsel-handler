"""Borsel Handler — Interactive Financial Analytics Dashboard.

Streamlit frontend communicating exclusively via HTTP with the FastAPI backend.
No direct database access, no duplicate business logic, no direct Yahoo Finance fetching.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sys

# Ensure dashboard directory is in path when executing directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

from api_client import (
    ApiClientError,
    BackendUnavailableError,
    BorselApiClient,
    ResourceNotFoundError,
)
from charts import create_price_line_chart, create_volume_bar_chart
from styles import TERMINAL_CSS, render_kpi

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Borsel Handler | Indian Market Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom terminal dark styling
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# State and Client Initialization
# ---------------------------------------------------------------------------
api_url = os.getenv("BORSEL_API_URL", "http://localhost:8000")
client = BorselApiClient(base_url=api_url)

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "RELIANCE.NS"

if "refresh_msg" not in st.session_state:
    st.session_state.refresh_msg = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="terminal-brand">
            <span style="font-size: 1.8rem;">⚡</span>
            <div>
                <div class="terminal-title">Borsel Handler</div>
                <div class="terminal-subtitle">Market Data Terminal</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color: #1f2937; margin: 12px 0 16px 0;'>", unsafe_allow_html=True)

    # Backend Connection Status
    health = client.check_health()
    if health["is_healthy"]:
        st.markdown(
            f'<div style="margin-bottom: 12px;"><span class="badge badge-online">● Backend Online</span> '
            f'<span style="font-size: 0.72rem; color: #9ca3af; margin-left: 6px;">{health["url"]}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="margin-bottom: 12px;"><span class="badge badge-offline">● Backend Offline</span> '
            f'<span style="font-size: 0.72rem; color: #f87171; margin-left: 6px;">{health["url"]}</span></div>',
            unsafe_allow_html=True,
        )

    # Navigation Selection
    nav = st.radio(
        "Navigation",
        options=["📊 Market Overview", "📈 Stock Explorer", "⚡ Data Ingestion", "⚙️ System Status"],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color: #1f2937; margin: 18px 0;'>", unsafe_allow_html=True)

    # Quick Stock Switcher in Sidebar
    st.markdown("<div style='font-size: 0.75rem; text-transform: uppercase; color: #9ca3af; letter-spacing: 0.05em; margin-bottom: 6px;'>Active Stock</div>", unsafe_allow_html=True)
    symbol_options = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    curr_idx = symbol_options.index(st.session_state.selected_symbol) if st.session_state.selected_symbol in symbol_options else 0
    chosen_symbol = st.selectbox(
        "Select Active Symbol",
        options=symbol_options,
        index=curr_idx,
        label_visibility="collapsed",
        key="sidebar_symbol_picker",
    )
    if chosen_symbol != st.session_state.selected_symbol:
        st.session_state.selected_symbol = chosen_symbol

    st.markdown(
        """
        <div style="position: fixed; bottom: 20px; left: 20px; font-size: 0.72rem; color: #6b7280;">
            Borsel Handler MVP v1.0<br>
            Provider: Yahoo Finance
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# View 1: Market Overview
# ---------------------------------------------------------------------------
if nav == "📊 Market Overview":
    col_head_left, col_head_right = st.columns([3, 1])
    with col_head_left:
        st.markdown(
            """
            <div style="margin-bottom: 16px;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #ffffff;">Indian Market Data Overview</h1>
                <p style="margin: 2px 0 0 0; color: #9ca3af; font-size: 0.88rem;">
                    Daily OHLCV observations and pipeline status for major National Stock Exchange (NSE) securities
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_head_right:
        now_utc = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
        st.markdown(
            f"""
            <div style="text-align: right; margin-top: 6px;">
                <span class="badge badge-provider">Data: Yahoo Finance</span>
                <div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">Updated: {now_utc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not health["is_healthy"]:
        st.error(
            f"⚠️ **FastAPI Backend Unreachable**: Cannot connect to `{api_url}`. "
            "Please ensure the Docker containers are running (`docker-compose up -d`) and retry."
        )
        if st.button("🔄 Retry Connection"):
            st.rerun()
    else:
        try:
            summary = client.get_summary()
            stocks_data = client.get_stocks()

            # Render KPI Cards
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                total_rec = f"{summary.get('total_records', 0):,}"
                st.markdown(render_kpi("Total Records Stored", total_rec, "Daily historical OHLCV rows"), unsafe_allow_html=True)
            with k2:
                num_stocks = str(len(summary.get("tracked_stocks", [])))
                st.markdown(render_kpi("Tracked Securities", f"{num_stocks} Stocks", "NSE Bluechips"), unsafe_allow_html=True)
            with k3:
                latest_date = summary.get("latest_date") or summary.get("latest_trading_date") or "N/A"
                st.markdown(render_kpi("Latest Trading Date", str(latest_date), "Most recent market session"), unsafe_allow_html=True)
            with k4:
                latest_run = summary.get("latest_run")
                run_status = latest_run.get("status", "N/A") if latest_run else "None"
                sub_type = "success" if run_status == "COMPLETED" else ("warning" if run_status == "PARTIAL" else "normal")
                run_time = latest_run.get("completed_at")[:16].replace("T", " ") if (latest_run and latest_run.get("completed_at")) else "Pending"
                st.markdown(render_kpi("Ingestion Status", run_status, f"Run: {run_time}", subtext_type=sub_type), unsafe_allow_html=True)

            # Section: Stock Watchlist
            st.markdown(
                """
                <div class="section-header">
                    <span class="section-title">Stock Watchlist</span>
                    <span class="section-subtitle">Real-time database records summary across tracked assets</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if stocks_data:
                rows = []
                for s in stocks_data:
                    rows.append({
                        "Symbol": s["symbol"],
                        "Latest Close": f"₹{s['latest_close']:,.2f}" if s.get("latest_close") is not None else "N/A",
                        "Latest Date": s.get("last_date") or s.get("latest_trading_date") or "N/A",
                        "Records": s.get("record_count", 0),
                        "Data Source": s.get("data_source", "Yahoo Finance"),
                    })
                df_watchlist = pd.DataFrame(rows)

                # Display table with selection column
                c_tbl, c_chart = st.columns([1.1, 0.9])
                with c_tbl:
                    st.dataframe(
                        df_watchlist,
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption("Select a stock from the sidebar or click into the Stock Explorer tab to view deep charts.")

                with c_chart:
                    # Quick mini bar comparison of latest close
                    chart_df = pd.DataFrame([
                        {"Symbol": s["symbol"].replace(".NS", ""), "Close": s.get("latest_close") or 0.0}
                        for s in stocks_data
                    ])
                    import plotly.express as px
                    bar_fig = px.bar(
                        chart_df,
                        x="Symbol",
                        y="Close",
                        title="Latest Closing Prices Comparison (₹)",
                        text_auto=",.0f",
                    )
                    bar_fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="#111827",
                        plot_bgcolor="#111827",
                        margin=dict(l=20, r=20, t=35, b=20),
                        height=240,
                        yaxis=dict(showgrid=True, gridcolor="rgba(255, 255, 255, 0.06)", tickprefix="₹"),
                    )
                    bar_fig.update_traces(marker_color="#0ea5e9")
                    st.plotly_chart(bar_fig, use_container_width=True)

        except ApiClientError as e:
            st.error(f"Error loading market summary: {e}")


# ---------------------------------------------------------------------------
# View 2: Historical Stock Explorer
# ---------------------------------------------------------------------------
elif nav == "📈 Stock Explorer":
    symbol = st.session_state.selected_symbol

    col_title, col_ctrl1, col_ctrl2 = st.columns([2.5, 1, 1])
    with col_title:
        st.markdown(
            f"""
            <div>
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #ffffff;">{symbol} Historical Explorer</h1>
                <p style="margin: 2px 0 0 0; color: #9ca3af; font-size: 0.88rem;">
                    Granular OHLCV prices, volume distributions, and price action analytics
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_ctrl1:
        chart_style = st.selectbox("Chart Style", options=["Line", "Candlestick"], index=0)
    with col_ctrl2:
        history_limit = st.selectbox("History Limit", options=[100, 250, 500, 1000], index=1)

    if not health["is_healthy"]:
        st.error("⚠️ Backend API is currently unavailable.")
    else:
        try:
            records = client.get_stock_history(symbol=symbol, limit=history_limit, order="asc")

            if not records:
                st.warning(f"No price records found for {symbol}. Run an ingestion refresh.")
            else:
                df = pd.DataFrame(records)
                df["trading_date"] = pd.to_datetime(df["trading_date"])
                df = df.sort_values("trading_date", ascending=True).reset_index(drop=True)

                latest_row = df.iloc[-1]
                prev_row = df.iloc[-2] if len(df) > 1 else latest_row
                daily_diff = latest_row["close"] - prev_row["close"]
                pct_diff = (daily_diff / prev_row["close"] * 100) if prev_row["close"] else 0.0

                # Top Metric Highlights
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                with m1:
                    st.metric(
                        "Latest Close",
                        f"₹{latest_row['close']:,.2f}",
                        f"{daily_diff:+,.2f} ({pct_diff:+.2f}%)",
                    )
                with m2:
                    st.metric("Open", f"₹{latest_row['open']:,.2f}")
                with m3:
                    st.metric("High", f"₹{latest_row['high']:,.2f}")
                with m4:
                    st.metric("Low", f"₹{latest_row['low']:,.2f}")
                with m5:
                    adj_str = f"₹{latest_row['adjusted_close']:,.2f}" if pd.notnull(latest_row.get("adjusted_close")) else "N/A"
                    st.metric("Adj Close", adj_str)
                with m6:
                    vol_str = f"{latest_row['volume']:,}"
                    st.metric("Volume", vol_str)

                # Charts
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                price_fig = create_price_line_chart(df, symbol=symbol, chart_type=chart_style)
                st.plotly_chart(price_fig, use_container_width=True)

                vol_fig = create_volume_bar_chart(df, symbol=symbol)
                st.plotly_chart(vol_fig, use_container_width=True)

                # Historical Data Table
                st.markdown(
                    """
                    <div class="section-header">
                        <span class="section-title">Historical Observations Data Table</span>
                        <span class="section-subtitle">Chronological record breakdown</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                df_display = df.copy()
                df_display["trading_date"] = df_display["trading_date"].dt.strftime("%Y-%m-%d")
                df_display = df_display.sort_values("trading_date", ascending=False)
                
                table_cols = ["trading_date", "open", "high", "low", "close", "adjusted_close", "volume", "data_source"]
                col_rename = {
                    "trading_date": "Trading Date",
                    "open": "Open (₹)",
                    "high": "High (₹)",
                    "low": "Low (₹)",
                    "close": "Close (₹)",
                    "adjusted_close": "Adj Close (₹)",
                    "volume": "Volume",
                    "data_source": "Source",
                }
                
                st.dataframe(
                    df_display[[c for c in table_cols if c in df_display.columns]].rename(columns=col_rename),
                    use_container_width=True,
                    hide_index=True,
                )

                # Download CSV
                csv_bytes = df_display.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Download {symbol} Historical Data (CSV)",
                    data=csv_bytes,
                    file_name=f"{symbol}_historical_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

        except ApiClientError as e:
            st.error(f"Error fetching data for {symbol}: {e}")


# ---------------------------------------------------------------------------
# View 3: Data Ingestion
# ---------------------------------------------------------------------------
elif nav == "⚡ Data Ingestion":
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #ffffff;">Market Data Ingestion Pipeline</h1>
            <p style="margin: 2px 0 0 0; color: #9ca3af; font-size: 0.88rem;">
                Trigger on-demand market data synchronization and monitor background audit execution runs
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not health["is_healthy"]:
        st.error("⚠️ Backend API is offline. Cannot trigger ingestion or fetch audit logs.")
    else:
        # Ingestion Trigger Card
        st.markdown(
            """
            <div class="kpi-container" style="padding: 20px 24px;">
                <div style="font-size: 1.05rem; font-weight: 600; color: #f3f4f6; margin-bottom: 4px;">Synchronize Historical Data</div>
                <div style="font-size: 0.82rem; color: #9ca3af; margin-bottom: 16px;">
                    Fetches real OHLCV data for all 5 tracked NSE tickers from Yahoo Finance, validates price rules, and idempotently upserts records.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Flash message if previously refreshed
        if st.session_state.refresh_msg:
            msg = st.session_state.refresh_msg
            run_id_short = str(msg.get("run_id", ""))[:8]
            st.success(f"✅ **{msg.get('message', 'Refresh completed')}** (Run ID: `{run_id_short}...`)")
            st.session_state.refresh_msg = None

        c_per, c_btn, c_space = st.columns([1.5, 1.5, 3])
        with c_per:
            period_choice = st.selectbox(
                "Ingestion Period",
                options=["1y", "6mo", "3mo", "1mo", "2y"],
                index=0,
                help="Historical window to request from Yahoo Finance",
            )
        with c_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            refresh_clicked = st.button("⚡ Trigger Market Data Refresh", type="primary", use_container_width=True)

        if refresh_clicked:
            with st.spinner(f"Ingesting {period_choice} market data from Yahoo Finance for 5 securities..."):
                try:
                    res = client.trigger_refresh(period=period_choice)
                    run_id_short = str(res.get('run_id', ''))[:8]
                    st.success(
                        f"✅ **{res.get('message', 'Market data refresh completed')}** (Run ID: `{run_id_short}...`)"
                    )
                    st.session_state.refresh_msg = res
                    st.rerun()
                except ApiClientError as err:
                    st.error(f"❌ Ingestion failed: {err}")

        # Ingestion History Table
        st.markdown(
            """
            <div class="section-header">
                <span class="section-title">Recent Ingestion Run History</span>
                <span class="section-subtitle">Audit records from ingestion.demo_import_runs</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            runs = client.get_ingestion_runs(limit=25)
            if not runs:
                st.info("No ingestion runs recorded yet.")
            else:
                formatted_runs = []
                for r in runs:
                    start_str = r["started_at"][:19].replace("T", " ") if r.get("started_at") else "N/A"
                    end_str = r["completed_at"][:19].replace("T", " ") if r.get("completed_at") else "Running"
                    formatted_runs.append({
                        "Run ID": str(r["id"])[:8] + "...",
                        "Started At (UTC)": start_str,
                        "Completed At (UTC)": end_str,
                        "Status": r.get("status", "UNKNOWN"),
                        "Provider": r.get("provider", "Yahoo Finance"),
                        "Processed": r.get("records_processed", 0),
                        "Failed": r.get("records_failed", 0),
                        "Error Details": r.get("error_message") or "—",
                    })
                df_runs = pd.DataFrame(formatted_runs)
                st.dataframe(df_runs, use_container_width=True, hide_index=True)
        except ApiClientError as err:
            st.error(f"Could not load ingestion audit runs: {err}")


# ---------------------------------------------------------------------------
# View 4: System Status
# ---------------------------------------------------------------------------
elif nav == "⚙️ System Status":
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color: #ffffff;">System Status & Architecture</h1>
            <p style="margin: 2px 0 0 0; color: #9ca3af; font-size: 0.88rem;">
                Platform connectivity, component health, and data integrity specifications
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        st.markdown(
            f"""
            <div class="kpi-container">
                <div class="section-title" style="margin-bottom: 12px;">FastAPI Backend Connectivity</div>
                <table style="width: 100%; font-size: 0.85rem; color: #d1d5db; line-height: 2;">
                    <tr><td><b>Backend URL:</b></td><td><code>{api_url}</code></td></tr>
                    <tr><td><b>Health Endpoint:</b></td><td><code>{api_url}/health</code></td></tr>
                    <tr><td><b>Connection Status:</b></td><td>
                        <span class="badge {'badge-online' if health['is_healthy'] else 'badge-offline'}">
                            {health['status'].upper()}
                        </span>
                    </td></tr>
                    <tr><td><b>Response:</b></td><td>{health['message']}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with s2:
        st.markdown(
            """
            <div class="kpi-container">
                <div class="section-title" style="margin-bottom: 12px;">Database Architecture & Integrity</div>
                <table style="width: 100%; font-size: 0.85rem; color: #d1d5db; line-height: 2;">
                    <tr><td><b>Database:</b></td><td>PostgreSQL 16 + TimescaleDB</td></tr>
                    <tr><td><b>MVP Demo Tables:</b></td><td><code>market.demo_daily_prices</code>, <code>ingestion.demo_import_runs</code></td></tr>
                    <tr><td><b>Reference Schema:</b></td><td>10 Core Models (Exchanges, Companies, Instruments, etc.)</td></tr>
                    <tr><td><b>Data Provider:</b></td><td><span class="badge badge-provider">Yahoo Finance</span> (Real market data)</td></tr>
                    <tr><td><b>Fabricated Data:</b></td><td>Strictly Zero Synthetic Data</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="kpi-container" style="margin-top: 16px;">
            <div class="section-title" style="margin-bottom: 8px;">Active Securities Tracked</div>
            <div style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 12px;">
                The platform monitors five benchmark constituents of the National Stock Exchange of India (NSE):
            </div>
            <ul style="font-size: 0.85rem; color: #e5e7eb; line-height: 1.8;">
                <li><code>RELIANCE.NS</code> — Reliance Industries Limited (Energy & Conglomerate)</li>
                <li><code>TCS.NS</code> — Tata Consultancy Services Limited (IT Services)</li>
                <li><code>INFY.NS</code> — Infosys Limited (IT Services)</li>
                <li><code>HDFCBANK.NS</code> — HDFC Bank Limited (Banking & Financial Services)</li>
                <li><code>ICICIBANK.NS</code> — ICICI Bank Limited (Banking & Financial Services)</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
