"""
financials_news.py
Financial Statements, News & Events, an Analyst-style Summary (rule-based,
not a live LLM call), and a trend Prediction.

Import:
    from financials_news import (
        render_financial_statements, render_news,
        render_analyst_summary, render_prediction, compute_trend_outlook,
    )
"""

import numpy as np
import pandas as pd
import streamlit as st

from risk_signal import compute_rsi, compute_macd


# --------------------------------------------------------------------------
# 1. FINANCIAL STATEMENTS
# --------------------------------------------------------------------------

def _format_statement(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in df.columns]
    # Scale to millions for readability
    return (df / 1e6).round(2)


def render_financial_statements(ticker_obj):
    st.subheader("Financial Statements")
    st.caption("Figures in millions (local currency), most recent years as columns.")

    tab1, tab2, tab3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

    with tab1:
        try:
            income = _format_statement(ticker_obj.income_stmt)
            if income is not None and not income.empty:
                st.dataframe(income, width="stretch")
            else:
                st.info("Income statement data not available for this ticker.")
        except Exception:
            st.info("Income statement data not available for this ticker.")

    with tab2:
        try:
            balance = _format_statement(ticker_obj.balance_sheet)
            if balance is not None and not balance.empty:
                st.dataframe(balance, width="stretch")
            else:
                st.info("Balance sheet data not available for this ticker.")
        except Exception:
            st.info("Balance sheet data not available for this ticker.")

    with tab3:
        try:
            cashflow = _format_statement(ticker_obj.cashflow)
            if cashflow is not None and not cashflow.empty:
                st.dataframe(cashflow, width="stretch")
            else:
                st.info("Cash flow data not available for this ticker.")
        except Exception:
            st.info("Cash flow data not available for this ticker.")


# --------------------------------------------------------------------------
# 2. NEWS & EVENTS
# --------------------------------------------------------------------------

def render_news(ticker_obj, max_items: int = 8):
    st.subheader("News & Events")
    try:
        news_items = ticker_obj.news or []
    except Exception:
        news_items = []

    if not news_items:
        st.info("No recent news available for this ticker.")
        return

    for item in news_items[:max_items]:
        # yfinance news items can be nested under "content" depending on version
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        publisher = (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher")
        link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link")
        if not title:
            continue
        st.markdown(f"**{title}**")
        if publisher:
            st.caption(publisher)
        if link:
            st.markdown(f"[Read more]({link})")
        st.divider()


# --------------------------------------------------------------------------
# 3. ANALYST & AI-STYLE SUMMARY (rule-based natural-language generation)
# --------------------------------------------------------------------------

def render_analyst_summary(result: dict):
    st.subheader("Summary")
    st.caption("Auto-generated from the underlying data — not a substitute for professional analysis.")

    info = result.get("info", {})
    risk = result["risk"]
    signal = result["signal"]
    company = result["company_name"]

    sentences = []

    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth > 0.10:
            sentences.append(f"{company} has shown strong recent revenue growth of about {rev_growth*100:.1f}%.")
        elif rev_growth > 0:
            sentences.append(f"{company} has posted modest revenue growth of about {rev_growth*100:.1f}%.")
        else:
            sentences.append(f"{company}'s revenue has recently contracted by about {abs(rev_growth)*100:.1f}%.")

    margin = info.get("operatingMargins")
    if margin is not None:
        if margin > 0.20:
            sentences.append("Operating margins remain healthy relative to typical industry levels.")
        elif margin > 0:
            sentences.append("Operating margins are positive but comparatively thin.")
        else:
            sentences.append("The company is currently operating at a margin loss.")

    de = info.get("debtToEquity")
    if de is not None:
        if de < 50:
            sentences.append("Debt levels appear low relative to equity.")
        elif de < 150:
            sentences.append("Debt levels are moderate relative to equity.")
        else:
            sentences.append("Debt levels are relatively high relative to equity, which is worth monitoring.")

    pe = info.get("trailingPE")
    if pe is not None:
        if pe > 40:
            sentences.append(f"At a P/E of {pe:.1f}, the stock is trading at a rich valuation relative to typical market averages.")
        elif pe > 15:
            sentences.append(f"At a P/E of {pe:.1f}, valuation looks reasonable relative to typical market averages.")
        else:
            sentences.append(f"At a P/E of {pe:.1f}, the stock looks inexpensive relative to typical market averages.")

    sentences.append(
        f"The current risk index sits at {risk['risk_index']}/100, driven mainly by "
        f"{'volatility' if risk['volatility_annualized'] > 40 else 'a mix of factors'}."
    )
    sentences.append(f"Combining trend and momentum signals, the rule-based read is currently: {signal['decision']}.")

    st.write(" ".join(sentences))


# --------------------------------------------------------------------------
# 4. PREDICTION (educational, probability-flavored — NOT a real forecast)
# --------------------------------------------------------------------------

def compute_trend_outlook(result: dict) -> dict | None:
    """
    Shared helper: simple statistical trend projection, reused by both the
    detailed Trend Outlook panel and the plain-language Signal & Risk summary.
    Returns None if there isn't enough price history.
    """
    hist = result["history"]
    close = hist["Close"]

    if len(close) < 20:
        return None

    window = min(30, len(close))
    y = close.tail(window).values
    x = np.arange(window)
    slope, intercept = np.polyfit(x, y, 1)
    slope_pct = (slope / y.mean()) * 100

    rsi = compute_rsi(close).iloc[-1]
    macd_line, signal_line, _ = compute_macd(close)
    macd_bullish = macd_line.iloc[-1] > signal_line.iloc[-1]

    votes = 0
    total = 3
    if slope_pct > 0:
        votes += 1
    if macd_bullish:
        votes += 1
    if 40 <= rsi <= 65:
        votes += 1
    confidence = round((votes / total) * 100)

    if slope_pct > 0.15:
        direction, trend_label = "up", "Uptrend"
    elif slope_pct < -0.15:
        direction, trend_label = "down", "Downtrend"
    else:
        direction, trend_label = "sideways", "Sideways / Range-bound"

    if confidence >= 67:
        confidence_label = "Fairly likely"
    elif confidence >= 34:
        confidence_label = "Uncertain — mixed signals"
    else:
        confidence_label = "Low confidence"

    return {
        "direction": direction,
        "trend_label": trend_label,
        "confidence": confidence,
        "confidence_label": confidence_label,
    }


def render_prediction(result: dict):
    st.subheader("Trend Outlook")
    st.caption(
        "This is a simple statistical projection based on recent price history — "
        "not a guarantee of future performance. Markets are influenced by many "
        "factors this model does not capture."
    )

    outlook = compute_trend_outlook(result)
    if outlook is None:
        st.info("Not enough price history for a trend projection.")
        return

    arrow = {"up": "▲", "down": "▼", "sideways": "→"}[outlook["direction"]]
    c1, c2 = st.columns(2)
    c1.metric("Expected Trend", f"{arrow} {outlook['trend_label']}")
    c2.metric("Confidence", f"{outlook['confidence']}%")

    st.warning(
        "Forecasts are estimates based on historical patterns only and are "
        "not guarantees of future price movement. Do not treat this as financial advice."
    )
