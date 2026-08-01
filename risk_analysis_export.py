"""
risk_analysis_export.py
Extended Risk Analysis panel (beta, downside risk, best/worst day, gauges).

Import:
    from risk_analysis_export import render_extended_risk_analysis
"""

import streamlit as st


def render_extended_risk_analysis(result: dict):
    st.subheader("Risk Analysis")

    risk = result["risk"]
    ext = result["extended_risk"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily Volatility", f"{ext['daily_volatility_pct']}%")
    c2.metric("Annualized Volatility", f"{risk['volatility_annualized']}%")
    c3.metric("Max Drawdown", f"{risk['max_drawdown_pct']}%")
    c4.metric("Beta", ext["beta"] if ext["beta"] is not None else "N/A")

    c5, c6 = st.columns(2)
    c5.metric("Downside Risk (Ann.)", f"{ext['downside_risk_pct']}%")
    c6.metric("RSI (14)", risk["rsi"])

    c7, c8 = st.columns(2)
    c7.metric("Best Single Day", f"{ext['best_day_pct']:+.2f}%")
    c8.metric("Worst Single Day", f"{ext['worst_day_pct']:+.2f}%")

    idx = risk["risk_index"]
    if idx < 35:
        st.success(f"Overall Risk Index: {idx}/100 — Low")
    elif idx < 70:
        st.warning(f"Overall Risk Index: {idx}/100 — Moderate")
    else:
        st.error(f"Overall Risk Index: {idx}/100 — High")
