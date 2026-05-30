import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from scipy.stats import percentileofscore

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Multi-Timeframe Engine", layout="wide")
st.title("🏦 BTC Multi-Timeframe Institutional Engine")

# ==========================================================
# DATA (DIÁRIO + 4H)
# ==========================================================
@st.cache_data(ttl=3600)
def load_data():

    daily = yf.download(
        "BTC-USD",
        start="2010-07-17",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    h4 = yf.download(
        "BTC-USD",
        period="60d",
        interval="4h",
        auto_adjust=True,
        progress=False
    )

    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.get_level_values(0)

    if isinstance(h4.columns, pd.MultiIndex):
        h4.columns = h4.columns.get_level_values(0)

    daily.reset_index(inplace=True)
    h4.reset_index(inplace=True)

    return daily, h4


daily, h4 = load_data()

if daily.empty or h4.empty:
    st.error("Sem dados")
    st.stop()

# ==========================================================
# INDICADORES
# ==========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def stochastic_rsi(rsi_series, k=3, d=3):
    min_rsi = rsi_series.rolling(14).min()
    max_rsi = rsi_series.rolling(14).max()

    stoch = (rsi_series - min_rsi) / (max_rsi - min_rsi)
    k_line = stoch.rolling(k).mean()
    return k_line


def adx(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    plus_dm = high.diff()
    minus_dm = low.diff() * -1

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr_val = tr.rolling(period).mean()

    plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr_val)
    minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr_val)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.rolling(period).mean(), plus_di, minus_di


# ==========================================================
# ================= DAILY FRAME ============================
# ==========================================================
daily["EMA169"] = ema(daily["Close"], 169)
daily["RSI"] = rsi(daily["Close"], 14)
daily["ADX"], daily["DI+"], daily["DI-"] = adx(daily)

daily = daily.dropna().reset_index(drop=True)

price_d = daily["Close"].iloc[-1]
ema_d = daily["EMA169"].iloc[-1]
adx_d = daily["ADX"].iloc[-1]
di_plus_d = daily["DI+"].iloc[-1]
di_minus_d = daily["DI-"].iloc[-1]

daily_trend = (
    price_d > ema_d and
    adx_d > 20 and
    di_plus_d > di_minus_d
)

# ==========================================================
# ================= 4H FRAME ===============================
# ==========================================================
h4["RSI"] = rsi(h4["Close"], 14)
h4["STOCH_K"] = stochastic_rsi(h4["RSI"])
h4["VOL_MA20"] = h4["Volume"].rolling(20).mean()

h4 = h4.dropna().reset_index(drop=True)

price_h = h4["Close"].iloc[-1]
rsi_h = h4["RSI"].iloc[-1]
stoch_h = h4["STOCH_K"].iloc[-1]
vol_h = h4["Volume"].iloc[-1]
vol_ma_h = h4["VOL_MA20"].iloc[-1]

entry_signal = (
    rsi_h < 40 and
    stoch_h < 0.2 and
    vol_h > vol_ma_h
)

# ==========================================================
# SCORE FINAL
# ==========================================================
trend_score = 60 if daily_trend else 0
entry_score = 40 if entry_signal else 0

score = trend_score + entry_score

# ==========================================================
# UI
# ==========================================================
c1, c2, c3 = st.columns(3)

c1.metric("BTC Diário", f"${price_d:,.0f}")
c2.metric("EMA 169", f"${ema_d:,.0f}")
c3.metric("Score", f"{score}/100")

st.divider()

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if not daily_trend:
    st.error("🔴 SEM TENDÊNCIA (DIÁRIO NEGATIVO)")

elif not entry_signal:
    st.warning("🟡 TENDÊNCIA OK — AGUARDAR ENTRADA (4H)")

else:
    st.success("🟢 LONG SETUP CONFIRMADO (MULTI-TF)")

# ==========================================================
# SUMMARY
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Trend Diário": bool(daily_trend),
    "Entry 4H": bool(entry_signal),
    "Score": score,
    "RSI 4H": rsi_h,
    "Stoch 4H": stoch_h
})
