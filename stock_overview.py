"""
stock_overview.py
Company Overview, Key Statistics, Technical Indicators panel, and an
explainable Buy/Sell Meter (star ratings + overall score).

Import:
    from stock_overview import (
        render_company_overview, render_key_statistics,
        render_technical_indicators, render_buy_sell_meter,
    )
"""

import numpy as np
import pandas as pd
import streamlit as st

from risk_signal import (
    compute_rsi, compute_macd, compute_bollinger, compute_ema,
    compute_atr, compute_vwap, compute_stochastic,
)
from financials_news import compute_trend_outlook


def _fmt_large_number(n, currency_symbol=""):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    n = float(n)
    for unit, divisor in [("T", 1e12), ("B", 1e9), ("Cr", 1e7), ("M", 1e6), ("K", 1e3)]:
        if abs(n) >= divisor and unit in ("T", "B", "M", "K"):
            return f"{currency_symbol}{n / divisor:.2f}{unit}"
    return f"{currency_symbol}{n:.2f}"


def _fmt_pct(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    return f"{n * 100:.2f}%" if abs(n) < 5 else f"{n:.2f}%"


def _fmt_volume(n):
    """Share volume as a plain comma-separated integer (standard convention
    on quote pages), not abbreviated K/M/B like currency figures."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    return f"{int(n):,}"


def _safe(info, key, default="N/A"):
    val = info.get(key)
    return default if val is None else val


# --------------------------------------------------------------------------
# 1. COMPANY OVERVIEW
# --------------------------------------------------------------------------

def render_company_overview(result: dict):
    """First-glance overview card — company understandable in ~10 seconds."""
    info = result.get("info", {})
    currency_symbol = result["currency_symbol"]
    hist = result["history"]

    prev_close = info.get("previousClose") or (hist["Close"].iloc[-2] if len(hist) > 1 else None)
    last_price = result["last_price"]
    change = (last_price - prev_close) if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    arrow = "▲" if change >= 0 else "▼"
    color = "green" if change >= 0 else "red"

    name_col, price_col = st.columns([1.6, 1])
    with name_col:
        st.subheader(f"{result['company_name']} ({result['ticker']})")
    with price_col:
        st.markdown(
            f"<div style='text-align:right;'>"
            f"<span style='font-size:1.7rem; font-weight:800;'>{currency_symbol}{last_price:,.2f}</span><br>"
            f"<span style='color:{'#22c55e' if change >= 0 else '#ef4444'}; font-weight:700;'>"
            f"{arrow} {abs(change):.2f} ({change_pct:+.2f}%)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.write("")

    stats = [
        ("Market Cap", _fmt_large_number(info.get("marketCap"), currency_symbol)),
        ("Sector", _safe(info, "sector")),
        ("Industry", _safe(info, "industry")),
        ("Volume", _fmt_volume(info.get("volume"))),
        ("52W High", f"{currency_symbol}{info.get('fiftyTwoWeekHigh'):,.2f}" if info.get("fiftyTwoWeekHigh") else "N/A"),
        ("52W Low", f"{currency_symbol}{info.get('fiftyTwoWeekLow'):,.2f}" if info.get("fiftyTwoWeekLow") else "N/A"),
        ("P/E Ratio", round(info["trailingPE"], 2) if info.get("trailingPE") else "N/A"),
        ("Dividend Yield", _fmt_pct(info.get("dividendYield")) if info.get("dividendYield") else "N/A"),
    ]
    cols = st.columns(2)
    for i, (label, value) in enumerate(stats):
        with cols[i % 2]:
            st.metric(label, value)

    risk_index = result.get("risk", {}).get("risk_index")
    if risk_index is not None:
        risk_color = "#22c55e" if risk_index < 35 else "#f59e0b" if risk_index < 70 else "#ef4444"
        st.markdown(
            f"""
            <div style="margin-top: 0.7rem; padding: 14px 16px; border: 1px solid rgba(255,255,255,0.09); border-radius: 12px; background: rgba(255,255,255,0.025);">
                <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: rgba(255,255,255,0.58); margin-bottom: 6px;">Risk Index</div>
                <div style="font-size: 1.15rem; font-weight: 800; color: {risk_color};">{risk_index:.1f}/100</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    outlook = compute_trend_outlook(result)
    if outlook is not None:
        direction = outlook["direction"]
        arrow = {"up": "▲", "down": "▼", "sideways": "→"}[direction]
        color = {"up": "#22c55e", "down": "#ef4444", "sideways": "#f59e0b"}[direction]
        st.markdown(
            f"""
            <div style="margin-top: 0.7rem; padding: 14px 16px; border: 1px solid rgba(255,255,255,0.09); border-radius: 12px; background: rgba(255,255,255,0.025);">
                <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: rgba(255,255,255,0.58); margin-bottom: 6px;">Outlook</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: {color};">{arrow} {outlook['trend_label']}</div>
                <div style="margin-top: 6px; font-size: 0.92rem; color: rgba(255,255,255,0.78);">Confidence: {outlook['confidence_label']} ({outlook['confidence']}%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 70px'></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# 2. KEY STATISTICS
# --------------------------------------------------------------------------

def render_key_statistics(result: dict):
    info = result.get("info", {})
    currency_symbol = result["currency_symbol"]

    rows = [
        ("Market Cap", _fmt_large_number(info.get("marketCap"), currency_symbol)),
        ("P/E Ratio (TTM)", round(info["trailingPE"], 2) if info.get("trailingPE") else "N/A"),
        ("Forward P/E", round(info["forwardPE"], 2) if info.get("forwardPE") else "N/A"),
        ("EPS (TTM)", info.get("trailingEps", "N/A")),
        ("Return on Equity (ROE)", _fmt_pct(info.get("returnOnEquity")) if info.get("returnOnEquity") else "N/A"),
        ("Debt-to-Equity", round(info["debtToEquity"], 2) if info.get("debtToEquity") else "N/A"),
        ("Current Ratio", round(info["currentRatio"], 2) if info.get("currentRatio") else "N/A"),
        ("Dividend Yield", _fmt_pct(info.get("dividendYield")) if info.get("dividendYield") else "N/A"),
        ("Beta", round(info["beta"], 2) if info.get("beta") else "N/A"),
        ("Enterprise Value", _fmt_large_number(info.get("enterpriseValue"), currency_symbol)),
        ("Free Cash Flow", _fmt_large_number(info.get("freeCashflow"), currency_symbol)),
    ]

    df = pd.DataFrame(rows, columns=["Metric", "Value"])
    st.table(df.set_index("Metric"))


# --------------------------------------------------------------------------
# 3. TECHNICAL INDICATORS PANEL (value + plain-language interpretation)
# --------------------------------------------------------------------------

def render_technical_indicators(result: dict):
    hist = result["history"]
    close = hist["Close"]

    rsi = compute_rsi(close).iloc[-1]
    macd_line, signal_line, _ = compute_macd(close)
    macd_val, macd_sig = macd_line.iloc[-1], signal_line.iloc[-1]
    upper, mid, lower = compute_bollinger(close)
    ema20 = compute_ema(close, 20).iloc[-1]
    sma20 = close.rolling(20).mean().iloc[-1]
    atr = compute_atr(hist).iloc[-1] if len(hist) >= 14 else np.nan
    vwap = compute_vwap(hist).iloc[-1]
    k, d = compute_stochastic(hist)
    k_val, d_val = k.iloc[-1], d.iloc[-1]
    price = close.iloc[-1]

    def interp(label, condition_high, condition_low, high_text, low_text, mid_text="Neutral"):
        if condition_high:
            return f":red[{high_text}]" if "overbought" in high_text.lower() else f":green[{high_text}]"
        if condition_low:
            return f":green[{low_text}]" if "oversold" in low_text.lower() else f":red[{low_text}]"
        return mid_text

    rows = [
        ("RSI (14)", round(rsi, 1), interp("RSI", rsi > 70, rsi < 30, "Overbought zone", "Oversold zone")),
        ("MACD", round(macd_val, 2), "Bullish (MACD > Signal)" if macd_val > macd_sig else "Bearish (MACD < Signal)"),
        ("Bollinger Bands", f"{lower.iloc[-1]:.2f} – {upper.iloc[-1]:.2f}",
         interp("BB", price > upper.iloc[-1], price < lower.iloc[-1], "Price above upper band (overbought)", "Price below lower band (oversold)")),
        ("EMA (20)", round(ema20, 2), "Price above EMA (bullish)" if price > ema20 else "Price below EMA (bearish)"),
        ("SMA (20)", round(sma20, 2) if not np.isnan(sma20) else "N/A",
         "Price above SMA (bullish)" if not np.isnan(sma20) and price > sma20 else "Price below SMA (bearish)"),
        ("ATR (14)", round(atr, 2) if not np.isnan(atr) else "N/A", "Higher ATR = more volatility"),
        ("VWAP", round(vwap, 2) if not np.isnan(vwap) else "N/A",
         "Price above VWAP (buyers in control)" if not np.isnan(vwap) and price > vwap else "Price below VWAP (sellers in control)"),
        ("Stochastic %K/%D", f"{k_val:.1f} / {d_val:.1f}",
         interp("Stoch", k_val > 80, k_val < 20, "Overbought zone", "Oversold zone")),
    ]

    df = pd.DataFrame(rows, columns=["Indicator", "Value", "Interpretation"])
    st.dataframe(df, hide_index=True, width="stretch")


# --------------------------------------------------------------------------
# 4. BUY/SELL METER (explainable star ratings, NOT a "buy this" directive)
# --------------------------------------------------------------------------

def _stars(score_1_to_5: int) -> str:
    score_1_to_5 = max(1, min(5, round(score_1_to_5)))
    return "★" * score_1_to_5 + "☆" * (5 - score_1_to_5)


def render_price_direction_summary(result: dict):
    """
    Plain-language read of what the price is likely to do next — direction
    only (increase / decrease / stay about the same), with a qualitative
    confidence read instead of an exact number or price target.
    """
    outlook = compute_trend_outlook(result)
    if outlook is None:
        return

    direction_text = {
        "up": "increase",
        "down": "decrease",
        "sideways": "stay about the same",
    }[outlook["direction"]]
    color = {"up": "green", "down": "red", "sideways": "orange"}[outlook["direction"]]

    st.markdown(
        f"#### In simple terms: the price is likely to :{color}[**{direction_text}**] "
        f"in the near term."
    )
    st.caption(
        f"Confidence: {outlook['confidence_label']} — based on recent trend and "
        f"momentum patterns. This is a near-term directional read, not an exact "
        f"price target or a guarantee."
    )


def render_buy_sell_meter(result: dict):
    render_price_direction_summary(result)
    st.divider()

    hist = result["history"]
    close = hist["Close"]
    info = result.get("info", {})
    risk = result["risk"]

    price = close.iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else np.nan
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan

    # Trend: price vs moving averages
    if not np.isnan(sma200) and price > sma50 > sma200:
        trend_score = 5
    elif not np.isnan(sma200) and price < sma50 < sma200:
        trend_score = 1
    elif not np.isnan(sma50) and price > sma50:
        trend_score = 4
    elif not np.isnan(sma50):
        trend_score = 2
    else:
        trend_score = 3

    # Momentum: RSI + MACD
    rsi = risk["rsi"]
    macd_line, signal_line, _ = compute_macd(close)
    macd_bullish = macd_line.iloc[-1] > signal_line.iloc[-1]
    momentum_score = 3
    if 40 <= rsi <= 60 and macd_bullish:
        momentum_score = 4
    if rsi > 70:
        momentum_score = 2
    if rsi < 30:
        momentum_score = 3  # oversold isn't necessarily bad momentum-wise
    if macd_bullish and rsi < 70:
        momentum_score = min(momentum_score + 1, 5)
    if not macd_bullish:
        momentum_score = max(momentum_score - 1, 1)

    # Volatility: fewer stars = more volatile/risky (favorability framing)
    vol_pct = risk["volatility_annualized"]
    if vol_pct < 20:
        volatility_score = 5
    elif vol_pct < 35:
        volatility_score = 4
    elif vol_pct < 50:
        volatility_score = 3
    elif vol_pct < 70:
        volatility_score = 2
    else:
        volatility_score = 1

    # Growth: revenue/earnings growth from info
    rev_growth = info.get("revenueGrowth")
    earn_growth = info.get("earningsGrowth")
    growth_values = [g for g in (rev_growth, earn_growth) if g is not None]
    if growth_values:
        avg_growth = sum(growth_values) / len(growth_values)
        growth_score = 5 if avg_growth > 0.20 else 4 if avg_growth > 0.10 else 3 if avg_growth > 0 else 2 if avg_growth > -0.10 else 1
    else:
        growth_score = 3

    # Dividend
    div_yield = info.get("dividendYield")
    if div_yield is None:
        dividend_score = 1
    elif div_yield > 4:
        dividend_score = 5
    elif div_yield > 2:
        dividend_score = 4
    elif div_yield > 0.5:
        dividend_score = 3
    else:
        dividend_score = 2

    components = {
        "Trend": trend_score,
        "Momentum": momentum_score,
        "Volatility (lower risk = more stars)": volatility_score,
        "Growth": growth_score,
        "Dividend": dividend_score,
    }
    overall = round(sum(components.values()) / (5 * len(components)) * 100)

    st.subheader("Buy/Sell Meter")
    st.caption("An explainable, rule-based score from public data — not financial advice.")

    cols = st.columns(len(components))
    for col, (label, score) in zip(cols, components.items()):
        with col:
            st.markdown(f"**{label}**")
            st.markdown(f"### {_stars(score)}")

    st.markdown(f"## Overall Score: {overall} / 100")
    if overall >= 70:
        st.success("Score reflects generally favorable trend, momentum, and risk characteristics.")
    elif overall <= 40:
        st.warning("Score reflects weaker trend/momentum and/or elevated volatility.")
    else:
        st.info("Score reflects a mixed picture across the underlying factors.")
