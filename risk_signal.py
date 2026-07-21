"""
risk_signal.py
Buy / Don't-Buy recommendation + Risk Index for the stock analytics platform.

Drop this file next to your Streamlit app and import:
    from risk_signal import analyze_stock, render_risk_panel

Requires: yfinance, pandas, numpy, plotly, streamlit
"""

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import time


# --------------------------------------------------------------------------
# 1. INDICATOR CALCULATIONS
# --------------------------------------------------------------------------

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_bollinger(close: pd.Series, window=20, num_std=2):
    sma = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, sma, lower


def compute_ema(close: pd.Series, span: int = 20) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def compute_atr(hist: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def compute_vwap(hist: pd.DataFrame) -> pd.Series:
    """Cumulative VWAP over the fetched window (note: true VWAP typically
    resets daily on intraday data; this is a simplified running version)."""
    typical_price = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    cum_vol = hist["Volume"].cumsum().replace(0, np.nan)
    return (typical_price * hist["Volume"]).cumsum() / cum_vol


def compute_stochastic(hist: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = hist["Low"].rolling(k_period).min()
    high_max = hist["High"].rolling(k_period).max()
    denom = (high_max - low_min).replace(0, np.nan)
    percent_k = 100 * (hist["Close"] - low_min) / denom
    percent_d = percent_k.rolling(d_period).mean()
    return percent_k.fillna(50), percent_d.fillna(50)


def compute_extended_risk_stats(hist: pd.DataFrame, info: dict) -> dict:
    """Additional risk metrics for the Risk Analysis section: beta,
    downside risk, best/worst single-day move, daily volatility."""
    daily_returns = hist["Close"].pct_change().dropna()
    daily_vol = float(daily_returns.std() * 100) if len(daily_returns) else 0.0

    downside_returns = daily_returns[daily_returns < 0]
    downside_risk = float(downside_returns.std() * np.sqrt(252) * 100) if len(downside_returns) else 0.0

    best_day = float(daily_returns.max() * 100) if len(daily_returns) else 0.0
    worst_day = float(daily_returns.min() * 100) if len(daily_returns) else 0.0

    beta = info.get("beta")

    return {
        "daily_volatility_pct": round(daily_vol, 2),
        "downside_risk_pct": round(downside_risk, 2),
        "best_day_pct": round(best_day, 2),
        "worst_day_pct": round(worst_day, 2),
        "beta": round(beta, 2) if isinstance(beta, (int, float)) else None,
    }



def annualized_volatility(close: pd.Series, window=30) -> float:
    daily_returns = close.pct_change().dropna()
    if len(daily_returns) < window:
        window = len(daily_returns)
    vol = daily_returns.tail(window).std() * np.sqrt(252)
    return float(vol) if not np.isnan(vol) else 0.0


def max_drawdown(close: pd.Series) -> float:
    cum_max = close.cummax()
    drawdown = (close - cum_max) / cum_max
    return float(drawdown.min())  # negative number, e.g. -0.35


# --------------------------------------------------------------------------
# 2. RISK INDEX (0 = very low risk, 100 = very high risk)
# --------------------------------------------------------------------------

def compute_risk_index(hist: pd.DataFrame) -> dict:
    close = hist["Close"]

    vol = annualized_volatility(close)              # e.g. 0.15 - 1.0+
    dd = abs(max_drawdown(close))                    # e.g. 0.0 - 0.8+
    rsi = compute_rsi(close).iloc[-1]                 # 0-100
    volume_spike = hist["Volume"].tail(5).mean() / hist["Volume"].tail(60).mean() \
        if hist["Volume"].tail(60).mean() > 0 else 1.0

    # Normalize each component to 0-100 risk contribution
    vol_score = min(vol / 0.80, 1.0) * 100            # 80%+ annualized vol = max risk
    dd_score = min(dd / 0.60, 1.0) * 100              # 60%+ drawdown = max risk
    rsi_score = 100 - (100 - abs(rsi - 50) * 2)       # extreme RSI (overbought/oversold) = riskier
    rsi_score = abs(rsi - 50) * 2                     # 0 at RSI 50, 100 at RSI 0 or 100
    liquidity_score = min(abs(volume_spike - 1) * 50, 100)  # unusual volume = added risk

    # Weighted blend
    risk_index = (
        0.40 * vol_score +
        0.30 * dd_score +
        0.20 * rsi_score +
        0.10 * liquidity_score
    )
    risk_index = round(float(np.clip(risk_index, 0, 100)), 1)

    return {
        "risk_index": risk_index,
        "volatility_annualized": round(vol * 100, 2),
        "max_drawdown_pct": round(dd * 100, 2),
        "rsi": round(float(rsi), 1),
        "volume_spike_ratio": round(float(volume_spike), 2),
    }


# --------------------------------------------------------------------------
# 3. BUY / DON'T BUY DECISION
# --------------------------------------------------------------------------

def generate_signal(hist: pd.DataFrame, risk: dict) -> dict:
    close = hist["Close"]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
    price = close.iloc[-1]

    macd_line, signal_line, hist_bar = compute_macd(close)
    macd_bullish = macd_line.iloc[-1] > signal_line.iloc[-1]

    upper, sma20, lower = compute_bollinger(close)
    bb_position = (price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]) \
        if (upper.iloc[-1] - lower.iloc[-1]) != 0 else 0.5

    rsi = risk["rsi"]

    # Scoring: +1 bullish signal, -1 bearish signal
    score = 0
    reasons = []

    if not np.isnan(sma200):
        if price > sma50 > sma200:
            score += 2
            reasons.append("Price is above both the 50-day and 200-day moving averages (uptrend).")
        elif price < sma50 < sma200:
            score -= 2
            reasons.append("Price is below both the 50-day and 200-day moving averages (downtrend).")

    if macd_bullish:
        score += 1
        reasons.append("MACD line is above its signal line (bullish momentum).")
    else:
        score -= 1
        reasons.append("MACD line is below its signal line (bearish momentum).")

    if rsi < 30:
        score += 1
        reasons.append(f"RSI is {rsi} — potentially oversold.")
    elif rsi > 70:
        score -= 1
        reasons.append(f"RSI is {rsi} — potentially overbought.")

    if bb_position < 0.2:
        score += 1
        reasons.append("Price is near the lower Bollinger Band.")
    elif bb_position > 0.8:
        score -= 1
        reasons.append("Price is near the upper Bollinger Band.")

    if risk["risk_index"] > 70:
        score -= 1
        reasons.append("Overall risk index is high — elevated volatility/drawdown.")

    # Final decision
    if score >= 2 and risk["risk_index"] < 70:
        decision = "BUY"
    elif score <= -2 or risk["risk_index"] >= 80:
        decision = "DON'T BUY"
    else:
        decision = "HOLD / WATCH"

    return {"decision": decision, "score": score, "reasons": reasons}


CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
    "GBP": "£",
    "EUR": "€",
    "JPY": "¥",
    "CAD": "C$",
    "AUD": "A$",
    "HKD": "HK$",
    "SGD": "S$",
    "CNY": "¥",
}


def _quick_check(symbol: str) -> bool:
    """Return True if `symbol` returns real price history."""
    try:
        h = yf.Ticker(symbol).history(period="5d")
        return not h.empty
    except Exception:
        return False


def resolve_ticker(query: str) -> dict | None:
    """
    Accepts either a ticker ('AAPL', 'TCS.NS') or a company name
    ('Apple', 'Tata Consultancy Services') and resolves it to a valid
    Yahoo Finance ticker symbol, trying Indian exchanges (NSE/BSE) too.

    Returns {"symbol": ..., "name": ..., "exchange": ...} or None.
    """
    query = query.strip()
    if not query:
        return None

    # 1. If it already looks like a valid ticker (with or without exchange
    #    suffix), try it as-is first — fastest path for direct ticker input.
    if _quick_check(query):
        try:
            info = yf.Ticker(query).info
        except Exception:
            info = {}
        return {
            "symbol": query.upper(),
            "name": info.get("shortName", query.upper()),
            "exchange": info.get("exchange", ""),
        }

    # 2. Try Yahoo's search endpoint to resolve a company name (or partial
    #    ticker) to real listings — this also naturally surfaces NSE/BSE
    #    listings for Indian companies (e.g. "Tata Motors" -> TATAMOTORS.NS).
    try:
        search_results = yf.Search(query, max_results=8).quotes
    except Exception:
        search_results = []

    equity_results = [
        r for r in search_results
        if r.get("quoteType") in ("EQUITY", None) and r.get("symbol")
    ]

    if equity_results:
        # Prefer NSE/BSE if the query hints at India, otherwise take the
        # top-ranked match as returned by Yahoo's own relevance ranking.
        india_hint = any(word in query.lower() for word in ["india", "nse", "bse", "ltd", "limited"])
        if india_hint:
            for r in equity_results:
                if r["symbol"].endswith(".NS") or r["symbol"].endswith(".BO"):
                    return {
                        "symbol": r["symbol"],
                        "name": r.get("shortname") or r.get("longname") or r["symbol"],
                        "exchange": r.get("exchange", ""),
                    }
        top = equity_results[0]
        return {
            "symbol": top["symbol"],
            "name": top.get("shortname") or top.get("longname") or top["symbol"],
            "exchange": top.get("exchange", ""),
        }

    # 3. Last resort: brute-force common Indian suffixes in case search
    #    failed but the raw symbol is valid on NSE or BSE.
    for suffix in (".NS", ".BO"):
        candidate = f"{query.upper()}{suffix}"
        if _quick_check(candidate):
            try:
                info = yf.Ticker(candidate).info
            except Exception:
                info = {}
            return {
                "symbol": candidate,
                "name": info.get("shortName", candidate),
                "exchange": info.get("exchange", ""),
            }

    return None


def analyze_stock(query: str, period: str = "1y") -> dict:
    """
    Full pipeline: resolve ticker/company name (US or Indian), fetch data,
    compute risk index, generate signal.
    `query` can be a ticker ('AAPL', 'TCS.NS') or a company name
    ('Apple', 'Tata Consultancy Services').
    """
    resolved = resolve_ticker(query)
    if resolved is None:
        return {"error": f"Could not find a matching stock for '{query}'. "
                          f"Try the exact ticker (e.g. 'TCS.NS' for NSE, 'TCS.BO' for BSE)."}

    symbol = resolved["symbol"]
    ticker_obj = yf.Ticker(symbol)
    # auto_adjust=False keeps raw (unadjusted) close prices, which match what
    # you see on live quote pages — the default adjusted close can differ
    # slightly around dividends/splits.
    hist = ticker_obj.history(period=period, auto_adjust=False)
    if hist.empty:
        return {"error": f"No price history found for '{symbol}'."}

    # Some tickers (thinly traded stocks, holidays, newly-listed IPOs) return
    # trailing rows with NaN Close/Volume — drop those so calculations and
    # the displayed price are never NaN.
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        return {"error": f"No valid price data found for '{symbol}'."}

    try:
        currency = ticker_obj.info.get("currency", "USD")
    except Exception:
        currency = "USD"
    currency_symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")

    try:
        info = ticker_obj.info
    except Exception:
        info = {}

    risk = compute_risk_index(hist)
    signal = generate_signal(hist, risk)
    extended_risk = compute_extended_risk_stats(hist, info)

    # Prefer the live/last-traded price (fast_info) over the historical
    # daily close, since the latter can lag by a day or reflect a stale
    # session close depending on market hours.
    last_price = hist["Close"].iloc[-1]
    try:
        live_price = ticker_obj.fast_info.get("last_price")
        if live_price:
            last_price = live_price
    except Exception:
        pass

    return {
        "ticker": symbol,
        "company_name": resolved["name"],
        "exchange": resolved["exchange"],
        "currency": currency,
        "currency_symbol": currency_symbol,
        "last_price": round(float(last_price), 2),
        "risk": risk,
        "extended_risk": extended_risk,
        "signal": signal,
        "history": hist,
        "info": info,
        "ticker_obj": ticker_obj,
    }


# --------------------------------------------------------------------------
# 4. LIVE PRICE CHART
# --------------------------------------------------------------------------

# Timeframe presets: label -> (period, interval)
CHART_TIMEFRAMES = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
}


def get_chart_data(symbol: str, timeframe_label: str = "1D") -> pd.DataFrame:
    """
    Fetch price history for charting at the right granularity for the
    selected timeframe. Intraday intervals (e.g. 5m) give a "live" intraday
    view during market hours; longer timeframes fall back to daily/weekly
    candles. Note: Yahoo Finance intraday data is typically ~15 min delayed,
    not true real-time tick data.
    """
    period, interval = CHART_TIMEFRAMES.get(timeframe_label, ("1d", "5m"))
    hist = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    return hist.dropna(subset=["Close"])


def render_price_chart(hist: pd.DataFrame, ticker: str, company_name: str,
                        currency_symbol: str, timeframe_label: str = "1D"):
    """Render an interactive candlestick + volume chart with SMA/Bollinger overlays."""
    if hist.empty:
        st.warning("No chart data available for this timeframe.")
        return

    show_sma = st.checkbox("Show moving averages (20/50)", value=True, key=f"sma_{ticker}")
    show_bb = st.checkbox("Show Bollinger Bands", value=False, key=f"bb_{ticker}")

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25], vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"],
        name=ticker, increasing_line_color="#2ecc71", decreasing_line_color="#e74c3c",
    ), row=1, col=1)

    if show_sma and len(hist) >= 20:
        fig.add_trace(go.Scatter(
            x=hist.index, y=hist["Close"].rolling(20).mean(),
            line=dict(color="#f39c12", width=1.3), name="SMA 20",
        ), row=1, col=1)
    if show_sma and len(hist) >= 50:
        fig.add_trace(go.Scatter(
            x=hist.index, y=hist["Close"].rolling(50).mean(),
            line=dict(color="#3498db", width=1.3), name="SMA 50",
        ), row=1, col=1)

    if show_bb:
        upper, mid, lower = compute_bollinger(hist["Close"])
        fig.add_trace(go.Scatter(x=hist.index, y=upper, line=dict(color="#9b59b6", width=1, dash="dot"),
                                  name="BB Upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=lower, line=dict(color="#9b59b6", width=1, dash="dot"),
                                  name="BB Lower", fill="tonexty",
                                  fillcolor="rgba(155,89,182,0.08)"), row=1, col=1)

    volume_colors = np.where(hist["Close"] >= hist["Open"], "#2ecc71", "#e74c3c")
    fig.add_trace(go.Bar(
        x=hist.index, y=hist["Volume"], name="Volume",
        marker_color=volume_colors, showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        title=f"{company_name} ({ticker}) — {timeframe_label}",
        xaxis_rangeslider_visible=False,
        height=520,
        margin=dict(t=50, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text=f"Price ({currency_symbol.strip()})", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    st.plotly_chart(fig, width="stretch")

    last_price = hist["Close"].iloc[-1]
    prev_price = hist["Close"].iloc[0]
    change = last_price - prev_price
    change_pct = (change / prev_price * 100) if prev_price else 0
    arrow = "▲" if change >= 0 else "▼"
    color = "green" if change >= 0 else "red"
    st.markdown(
        f"**{currency_symbol}{last_price:.2f}** &nbsp; "
        f":{color}[{arrow} {abs(change):.2f} ({change_pct:+.2f}%)] "
        f"over {timeframe_label}"
    )


def render_live_chart_section(ticker: str, company_name: str, currency_symbol: str):
    """
    Full chart widget: timeframe selector + optional auto-refresh, to be
    called right after render_risk_panel() for the same searched stock.
    """
    st.subheader("Price Chart")

    col_tf, col_refresh = st.columns([3, 1])
    with col_tf:
        timeframe_label = st.radio(
            "Timeframe", list(CHART_TIMEFRAMES.keys()),
            index=0, horizontal=True, key=f"tf_{ticker}",
        )
    with col_refresh:
        auto_refresh = st.checkbox("Live (30s refresh)", key=f"auto_{ticker}")

    chart_data = get_chart_data(ticker, timeframe_label)
    render_price_chart(chart_data, ticker, company_name, currency_symbol, timeframe_label)

    if auto_refresh:
        st.caption("Auto-refreshing every 30 seconds. Data is delayed ~15 min (Yahoo Finance), not tick-by-tick.")
        time.sleep(30)
        st.rerun()


def _risk_gauge(risk_index: float) -> go.Figure:
    if risk_index < 35:
        bar_color = "#2ecc71"
    elif risk_index < 70:
        bar_color = "#f1c40f"
    else:
        bar_color = "#e74c3c"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk_index,
        number={"suffix": " / 100"},
        title={"text": "Risk Index"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": bar_color},
            "steps": [
                {"range": [0, 35], "color": "#eafaf1"},
                {"range": [35, 70], "color": "#fef9e7"},
                {"range": [70, 100], "color": "#fdedec"},
            ],
        },
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
    return fig


def render_risk_panel(result: dict):
    """Call this inside your Streamlit app to display the recommendation."""
    if "error" in result:
        st.error(result["error"])
        return

    if result.get("last_price") is None or np.isnan(result["last_price"]):
        st.error("Price data for this stock looks incomplete right now — try again in a moment.")
        return

    decision = result["signal"]["decision"]
    badge_colors = {
        "BUY": ("#22c55e", "rgba(34,197,94,0.12)"),
        "HOLD / WATCH": ("#f59e0b", "rgba(245,158,11,0.12)"),
        "DON'T BUY": ("#ef4444", "rgba(239,68,68,0.12)"),
    }
    text_color, bg_color = badge_colors[decision]

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(
            f"<div style='display:inline-block; font-size:1.15rem; font-weight:800; "
            f"color:{text_color}; background:{bg_color}; padding:8px 16px; "
            f"border-radius:8px; margin-bottom:6px;'>{decision}</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{result.get('company_name', result['ticker'])} · {result['ticker']}"
                   + (f" · {result['exchange']}" if result.get("exchange") else ""))
        st.metric("Last Price", f"{result['currency_symbol']}{result['last_price']}")
        st.write("**Why:**")
        for reason in result["signal"]["reasons"]:
            st.write(f"- {reason}")

    with col2:
        st.plotly_chart(_risk_gauge(result["risk"]["risk_index"]), width="stretch")

    with st.expander("Risk component breakdown"):
        r = result["risk"]
        st.write(f"- Annualized volatility: {r['volatility_annualized']}%")
        st.write(f"- Max drawdown (period): {r['max_drawdown_pct']}%")
        st.write(f"- RSI: {r['rsi']}")
        st.write(f"- Recent vs. average volume ratio: {r['volume_spike_ratio']}x")
