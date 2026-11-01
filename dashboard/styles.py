"""Custom CSS styles for Borsel Handler Dark Financial Analytics Terminal Theme."""

TERMINAL_CSS = """
<style>
/* Main App Styling */
.stApp {
    background-color: #0b0f19;
    color: #f3f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #0d121f !important;
    border-right: 1px solid #1f2937;
}

/* Header branding */
.terminal-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
}
.terminal-title {
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    margin: 0;
}
.terminal-subtitle {
    font-size: 0.85rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}

/* KPI Card Grid */
.kpi-container {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: border-color 0.15s ease-in-out;
}
.kpi-container:hover {
    border-color: #374151;
}
.kpi-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9ca3af;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.65rem;
    font-weight: 700;
    color: #f9fafb;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
.kpi-subtext {
    font-size: 0.78rem;
    color: #6b7280;
    margin-top: 4px;
}
.kpi-subtext-success {
    color: #10b981;
}
.kpi-subtext-warning {
    color: #f59e0b;
}

/* Status Badges */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
.badge-online {
    background-color: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
}
.badge-offline {
    background-color: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
.badge-provider {
    background-color: rgba(14, 165, 233, 0.15);
    color: #38bdf8;
    border: 1px solid rgba(14, 165, 233, 0.3);
}
.badge-completed {
    background-color: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.25);
}
.badge-failed {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.25);
}
.badge-partial {
    background-color: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.25);
}

/* Metric highlights */
.stock-metric-row {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 12px 0;
}
.stock-metric-item {
    flex: 1;
    min-width: 120px;
}
.stock-metric-name {
    font-size: 0.72rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stock-metric-val {
    font-size: 1.25rem;
    font-weight: 600;
    color: #f3f4f6;
}

/* Section dividers */
.section-header {
    border-bottom: 1px solid #1f2937;
    padding-bottom: 8px;
    margin: 24px 0 16px 0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}
.section-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #e5e7eb;
}
.section-subtitle {
    font-size: 0.82rem;
    color: #6b7280;
}

/* Clean dataframe tweaks */
[data-testid="stDataFrame"] {
    border: 1px solid #1f2937;
    border-radius: 6px;
    overflow: hidden;
}
</style>
"""


def render_kpi(label: str, value: str, subtext: str = "", subtext_type: str = "normal") -> str:
    """Helper to render an HTML KPI card."""
    sub_class = "kpi-subtext"
    if subtext_type == "success":
        sub_class += " kpi-subtext-success"
    elif subtext_type == "warning":
        sub_class += " kpi-subtext-warning"

    return f"""
    <div class="kpi-container">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="{sub_class}">{subtext}</div>
    </div>
    """
