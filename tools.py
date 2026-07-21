"""
tools.py
Returns Calculator, Compare Companies, and Watchlist.
(Portfolio Tracker intentionally excluded.)

Import:
    from tools import (
        render_returns_calculator, render_compare_companies, render_watchlist,
    )
"""

import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import yfinance as yf
import streamlit as st

from risk_signal import resolve_ticker, CURRENCY_SYMBOLS, compute_rsi, annualized_volatility

# --------------------------------------------------------------------------
# 1. RETURNS CALCULATOR
# --------------------------------------------------------------------------

def render_returns_calculator(ticker: str, currency_symbol: str):
    st.subheader("Returns Calculator")

    col1, col2 = st.columns(2)
    with col1:
        investment = st.number_input("Investment amount", min_value=0.0, value=10000.0, step=1000.0, key=f"inv_{ticker}")
    with col2:
        purchase_date = st.date_input(
            "Purchase date",
            value=datetime.date.today() - datetime.timedelta(days=365),
            max_value=datetime.date.today() - datetime.timedelta(days=1),
            key=f"date_{ticker}",
        )

    if st.button("Calculate", key=f"calc_{ticker}"):
        hist = yf.Ticker(ticker).history(start=purchase_date, auto_adjust=False)
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            st.error("No price data available for that date range.")
            return

        buy_price = hist["Close"].iloc[0]
        current_price = hist["Close"].iloc[-1]
        shares = investment / buy_price
        current_value = shares * current_price
        profit = current_value - investment
        return_pct = (profit / investment) * 100

        days_held = (hist.index[-1].date() - hist.index[0].date()).days
        years_held = max(days_held / 365.25, 1 / 365.25)
        annualized_return = ((current_value / investment) ** (1 / years_held) - 1) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Value", f"{currency_symbol}{current_value:,.2f}")
        c2.metric("Profit / Loss", f"{currency_symbol}{profit:,.2f}", f"{return_pct:+.2f}%")
        c3.metric("Total Return", f"{return_pct:+.2f}%")
        c4.metric("Annualized Return", f"{annualized_return:+.2f}%")


# --------------------------------------------------------------------------
# 2. COMPARE COMPANIES
# --------------------------------------------------------------------------

def render_compare_companies():
    st.subheader("Compare Companies")
    raw_input = st.text_input(
        "Enter 2–4 tickers or company names, comma-separated",
        "AAPL, MSFT, NVDA",
        key="compare_input",
    )
    if not st.button("Compare", key="compare_btn"):
        return

    queries = [q.strip() for q in raw_input.split(",") if q.strip()][:4]
    if len(queries) < 2:
        st.warning("Enter at least 2 companies to compare.")
        return

    rows = []
    with st.spinner("Fetching comparison data..."):
        for q in queries:
            resolved = resolve_ticker(q)
            if resolved is None:
                st.warning(f"Could not resolve '{q}' — skipping.")
                continue
            symbol = resolved["symbol"]
            t = yf.Ticker(symbol)
            hist = t.history(period="1y", auto_adjust=False).dropna(subset=["Close"])
            if hist.empty:
                continue
            try:
                info = t.info
            except Exception:
                info = {}
            currency_symbol = CURRENCY_SYMBOLS.get(info.get("currency", "USD"), "")
            price = hist["Close"].iloc[-1]
            year_return = (price / hist["Close"].iloc[0] - 1) * 100
            vol = annualized_volatility(hist["Close"]) * 100

            rows.append({
                "Ticker": symbol,
                "Name": resolved["name"],
                "Price": f"{currency_symbol}{price:,.2f}",
                "Market Cap": info.get("marketCap"),
                "P/E Ratio": round(info["trailingPE"], 2) if info.get("trailingPE") else "N/A",
                "Dividend Yield": f"{info['dividendYield']:.2f}%" if info.get("dividendYield") else "N/A",
                "1Y Return": f"{year_return:+.2f}%",
                "Volatility (Ann.)": f"{vol:.1f}%",
            })

    if not rows:
        st.error("Couldn't fetch data for any of the entered companies.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")

    chart_df = df.copy()
    chart_df["Market Cap ($B approx)"] = chart_df["Market Cap"].apply(
        lambda x: x / 1e9 if isinstance(x, (int, float)) else 0
    )
    fig = px.bar(chart_df, x="Ticker", y="Market Cap ($B approx)", title="Market Cap Comparison")
    st.plotly_chart(fig, width="stretch")


# --------------------------------------------------------------------------
# 3. WATCHLIST (session-based; swap for a DB table in production)
# --------------------------------------------------------------------------

def render_watchlist():
    st.subheader("Watchlist")

    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = []

    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("Add a company name or ticker", key="watchlist_add_input")
    with col2:
        st.write("")
        st.write("")
        if st.button("Add", key="watchlist_add_btn") and new_ticker.strip():
            resolved = resolve_ticker(new_ticker.strip())
            if resolved and resolved["symbol"] not in st.session_state["watchlist"]:
                st.session_state["watchlist"].append(resolved["symbol"])
            elif not resolved:
                st.warning(f"Couldn't resolve '{new_ticker}'.")

    if not st.session_state["watchlist"]:
        st.info("Your watchlist is empty — add a ticker above.")
        return

    rows = []
    for symbol in st.session_state["watchlist"]:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d", auto_adjust=False).dropna(subset=["Close"])
            if len(hist) < 1:
                continue
            info = t.info
            currency_symbol = CURRENCY_SYMBOLS.get(info.get("currency", "USD"), "")
            price = hist["Close"].iloc[-1]
            change_pct = (price / hist["Close"].iloc[-2] - 1) * 100 if len(hist) > 1 else 0.0
            rows.append({
                "Ticker": symbol,
                "Name": info.get("shortName", symbol),
                "Price": f"{currency_symbol}{price:,.2f}",
                "Change %": round(change_pct, 2),
            })
        except Exception:
            continue

    if rows:
        df = pd.DataFrame(rows).sort_values("Change %", ascending=False)
        st.dataframe(df, hide_index=True, width="stretch")

    remove_choice = st.selectbox("Remove from watchlist", [""] + st.session_state["watchlist"])
    if remove_choice and st.button("Remove"):
        st.session_state["watchlist"].remove(remove_choice)
        st.rerun()