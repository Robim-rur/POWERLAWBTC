import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Live Engine", layout="wide")
st.title("🏦 BTC Live Engine (Stable Mode)")

# ==========================================================
# DATA (POLLING REAL)
# ==========================================================
@st.cache_data(ttl=10)  # atualiza a cada 10s
def get_data():
    df = yf.download(
        "BTC-USD",
        period="5d",
        interval="5m",
        auto_adjust=True,
        progress=False
    )

    df = df.reset_index()
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    return df


df = get_data()

# ==========================================================
# INDICADORES
# ==========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


df["EMA20"] = ema(df["Close"], 20)

price = df["Close"].iloc[-1]
ema20 = df["EMA20"].iloc[-1]

trend = price > ema20

# ==========================================================
# SIGNAL
# ==========================================================
if trend:
    signal = "🟢 FLUXO POSITIVO"
else:
    signal = "🔴 FLUXO NEGATIVO"

# ==========================================================
# UI
# ==========================================================
c1, c2 = st.columns(2)

c1.metric("BTC", f"${price:,.2f}")
c2.metric("EMA 20", f"${ema20:,.2f}")

st.divider()

if trend:
    st.success(signal)
else:
    st.error(signal)

# ==========================================================
# CHART
# ==========================================================
st.line_chart(df.set_index("Datetime")["Close"])

st.caption("Atualização automática via polling (10s)")
