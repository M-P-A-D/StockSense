"""
demo_app.py
Stock analytics platform — wires together risk_signal.py, stock_overview.py,
financials_news.py, risk_analysis_export.py, and tools.py.

Run with:
    python -m streamlit run demo_app.py

Portfolio Tracker, Screener, and Heatmap are intentionally NOT included.
"""

import streamlit as st

from risk_signal import analyze_stock, render_risk_panel, render_live_chart_section
from stock_overview import (
    render_company_overview, render_key_statistics,
    render_technical_indicators, render_buy_sell_meter,
)
from financials_news import (
    render_financial_statements, render_news,
    render_analyst_summary, render_prediction,
)
from risk_analysis_export import render_extended_risk_analysis, render_export_section
from tools import render_returns_calculator, render_compare_companies, render_watchlist


# --------------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="StockSense — Analytics Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# GLOBAL STYLING
# --------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');

:root {
    --accent: #22c55e;
    --accent-dim: rgba(34, 197, 94, 0.12);
    --danger: #ef4444;
    --danger-dim: rgba(239, 68, 68, 0.12);
    --warn: #f59e0b;
    --card-bg: rgba(255, 255, 255, 0.025);
    --card-border: rgba(255, 255, 255, 0.09);
    --text-dim: rgba(255, 255, 255, 0.58);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
}
code, pre, .stCodeBlock {
    font-family: 'JetBrains Mono', monospace !important;
}

.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1200px; }

/* ---------- Masthead ---------- */
.ss-masthead {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 18px;
    margin-bottom: 22px;
    border-bottom: 1px solid var(--card-border);
}
.ss-brand { display: flex; align-items: center; gap: 12px; }
.ss-brand-icon {
    width: 42px; height: 42px; border-radius: 11px;
    background: linear-gradient(135deg, var(--accent), #16a34a);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(34,197,94,0.35);
}
.ss-brand-title { font-size: 1.35rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
.ss-brand-tag { font-size: 0.8rem; color: var(--text-dim); font-weight: 500; }
.ss-badge {
    font-size: 0.72rem; font-weight: 600; color: var(--text-dim);
    border: 1px solid var(--card-border); border-radius: 20px;
    padding: 5px 12px; background: var(--card-bg);
    display: inline-flex; align-items: center; gap: 7px;
}
.ss-live-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-dim);
    animation: ss-pulse 2s ease-in-out infinite;
}
@keyframes ss-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ---------- Metric cards ---------- */
div[data-testid="stMetric"] {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 16px 18px 12px 18px;
    transition: border-color 0.15s ease, transform 0.15s ease;
}
div[data-testid="stMetric"]:hover {
    border-color: rgba(34, 197, 94, 0.35);
    transform: translateY(-1px);
}
div[data-testid="stMetricLabel"] {
    font-size: 0.76rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; color: var(--text-dim) !important;
}
div[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; }

/* ---------- Native bordered containers (cards) ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border-color: var(--card-border) !important;
}

/* ---------- Tabs (pill style) ---------- */
div[data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--card-bg);
    padding: 5px;
    border-radius: 12px;
    border: 1px solid var(--card-border);
}
button[data-baseweb="tab"] {
    font-size: 0.88rem;
    font-weight: 600;
    padding: 9px 16px;
    border-radius: 9px !important;
    color: var(--text-dim);
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: var(--accent-dim);
    color: var(--accent) !important;
}
div[data-baseweb="tab-highlight"] { display: none; }

/* ---------- Buttons ---------- */
div.stButton > button, div.stDownloadButton > button {
    border-radius: 9px;
    font-weight: 600;
    border: 1px solid var(--card-border);
    transition: all 0.15s ease;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent), #16a34a);
    border: none;
    box-shadow: 0 3px 10px rgba(34,197,94,0.28);
}
div.stButton > button[kind="primary"]:hover {
    box-shadow: 0 5px 16px rgba(34,197,94,0.4);
    transform: translateY(-1px);
}

/* ---------- Inputs ---------- */
div[data-baseweb="input"], div[data-baseweb="select"] > div {
    border-radius: 9px !important;
}

/* ---------- Headings ---------- */
h2, h3 { font-weight: 700; letter-spacing: -0.01em; }
.stCaption, small { color: var(--text-dim) !important; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    border-right: 1px solid var(--card-border);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.8rem; }

/* ---------- Dataframes ---------- */
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* ---------- Dividers ---------- */
hr { margin: 1.3rem 0; border-color: var(--card-border); }

/* ---------- Feature grid (landing page) ---------- */
.ss-feature-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: var(--accent-dim); color: var(--accent);
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 10px;
}
.ss-feature-title { font-weight: 700; font-size: 0.95rem; margin-bottom: 3px; }
.ss-feature-desc { font-size: 0.83rem; color: var(--text-dim); line-height: 1.4; }

/* ---------- Footer ---------- */
.ss-footer {
    margin-top: 2.5rem; padding-top: 1.2rem;
    border-top: 1px solid var(--card-border);
    font-size: 0.78rem; color: var(--text-dim); text-align: center;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# MASTHEAD
# --------------------------------------------------------------------------

st.markdown("""
<div class="ss-masthead">
    <div class="ss-brand">
        <div class="ss-brand-icon">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="20" height="20">
                <path d="M3 17L9 11L13 15L21 6" stroke="#06170c" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M15 6H21V12" stroke="#06170c" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div>
            <div class="ss-brand-title">StockSense</div>
            <div class="ss-brand-tag">Real-time analytics & decision support</div>
        </div>
    </div>
    <div class="ss-badge"><span class="ss-live-dot"></span>Live data · Yahoo Finance</div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# SIDEBAR — search + watchlist
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("#### Search")
    query_input = st.text_input(
        "Company name or ticker",
        placeholder="e.g. Apple, AAPL, Tata Motors, TCS.NS",
        label_visibility="collapsed",
    )
    analyze_clicked = st.button("Analyze", type="primary", width="stretch")
    if analyze_clicked and query_input.strip():
        st.session_state["last_query"] = query_input.strip()

    st.caption("Quick picks")
    quick_cols = st.columns(2)
    quick_picks = ["AAPL", "MSFT", "TCS.NS", "RELIANCE.NS"]
    for i, symbol in enumerate(quick_picks):
        with quick_cols[i % 2]:
            if st.button(symbol, key=f"quick_{symbol}", width="stretch"):
                st.session_state["last_query"] = symbol

    st.divider()
    with st.expander("Watchlist", expanded=False):
        render_watchlist()

    st.divider()
    st.caption(
        "Data via Yahoo Finance, typically delayed ~15 min. "
        "Signals shown are rule-based and educational — not financial advice."
    )


# --------------------------------------------------------------------------
# MAIN CONTENT
# --------------------------------------------------------------------------

if "last_query" not in st.session_state:
    st.markdown("### Search a stock to get started")
    st.write(
        "Look up any US stock or Indian stock on NSE/BSE by name or ticker "
        "in the sidebar to get a full breakdown."
    )

    ICONS = {
        "chart": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 15l4-5 3 3 6-7"/>',
        "signal": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
        "sliders": '<line x1="4" y1="7" x2="20" y2="7"/><circle cx="9" cy="7" r="2" fill="currentColor" stroke="none"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none"/><line x1="4" y1="17" x2="20" y2="17"/><circle cx="11" cy="17" r="2" fill="currentColor" stroke="none"/>',
        "alert": '<path d="M12 3l9 16H3z"/><line x1="12" y1="10" x2="12" y2="14"/><circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none"/>',
        "document": '<path d="M6 2h9l5 5v15H6z"/><path d="M15 2v5h5"/><line x1="9" y1="13" x2="17" y2="13"/><line x1="9" y1="17" x2="17" y2="17"/>',
        "compare": '<path d="M7 3v18"/><path d="M17 3v18"/><path d="M3 7l4-4 4 4"/><path d="M13 17l4 4 4-4"/>',
    }

    def svg_icon(name, size=18):
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
                f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
                f'stroke-linejoin="round">{ICONS[name]}</svg>')

    features = [
        ("chart", "Live Charts", "Candlestick charts with SMA, Bollinger Bands, and volume across 6 timeframes."),
        ("signal", "Buy/Sell Signal", "An explainable, rule-based score across trend, momentum, and risk."),
        ("sliders", "Technical Indicators", "RSI, MACD, EMA, ATR, VWAP, and Stochastic with plain-language reads."),
        ("alert", "Risk Analysis", "Volatility, drawdown, beta, and a composite 0–100 risk index."),
        ("document", "Financials & News", "Income statement, balance sheet, cash flow, and recent headlines."),
        ("compare", "Compare & Calculate", "Side-by-side comparisons and a what-if returns calculator."),
    ]
    cols = st.columns(3)
    for i, (icon_name, title, desc) in enumerate(features):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f'<div class="ss-feature-icon">{svg_icon(icon_name)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-feature-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-feature-desc">{desc}</div>', unsafe_allow_html=True)

else:
    with st.spinner("Analyzing..."):
        result = analyze_stock(st.session_state["last_query"])

    if "error" in result:
        st.error(result["error"])
    else:
        with st.container(border=True):
            render_company_overview(result)

        st.write("")

        tabs = st.tabs([
            "Chart", "Signal & Risk", "Technicals",
            "Key Stats", "Financials & News", "Summary & Outlook",
            "Returns Calculator", "Compare", "Export",
        ])

        with tabs[0]:
            render_live_chart_section(
                ticker=result["ticker"],
                company_name=result["company_name"],
                currency_symbol=result["currency_symbol"],
            )

        with tabs[1]:
            render_buy_sell_meter(result)
            st.divider()
            render_risk_panel(result)
            st.divider()
            render_extended_risk_analysis(result)

        with tabs[2]:
            render_technical_indicators(result)

        with tabs[3]:
            render_key_statistics(result)

        with tabs[4]:
            render_financial_statements(result["ticker_obj"])
            st.divider()
            render_news(result["ticker_obj"])

        with tabs[5]:
            render_analyst_summary(result)
            st.divider()
            render_prediction(result)

        with tabs[6]:
            render_returns_calculator(result["ticker"], result["currency_symbol"])

        with tabs[7]:
            render_compare_companies()

        with tabs[8]:
            render_export_section(result)

st.markdown(
    '<div class="ss-footer">StockSense is an educational analytics tool. '
    'Nothing shown here is financial advice. Data may be delayed.</div>',
    unsafe_allow_html=True,
)
