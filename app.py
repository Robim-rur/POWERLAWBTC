import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Hedge Engine Stable", layout="wide")
st.title("🏦 BTC Hedge Engine — Final Stable v4")

# ==========================================================
# STATE
# ==========================================================
if "log" not in st.session_state:
    st.session_state.log = []

# ==========================================================
# DATA ENGINE (ROBUSTO)
# ==========================================================
def fetch_yahoo():

    df = yf.download(
        "BTC-USD",
        interval="1h",
        period="60d",
        auto_adjust=True,
        progress=False
    )

    if df is None or len(df) < 50:
        return pd.DataFrame()

    df = df.reset_index()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    time_col = df.columns[0]
    df.rename(columns={time_col: "Datetime"}, inplace=True)

    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    return df


df = fetch_yahoo()

if df.empty or len(df) < 50:
    st.error("Dataset insuficiente para cálculo seguro")
    st.stop()

# ==========================================================
# INDICATORS SAFE
# ==========================================================
def ema(series, period):
    return pd.Series(series).ewm(span=period, adjust=False).mean()


def rsi(series, period=14):

    series = np.asarray(series).reshape(-1)

    # 🔥 PROTEÇÃO CRÍTICA
    if len(series) < period + 2:
        return np.zeros(len(series))

    delta = np.diff(series, prepend=series[0])

    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    gain = pd.Series(gain)
    loss = pd.Series(loss)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return (100 - (100 / (1 + rs))).fillna(0)

# ==========================================================
# POWER LAW SAFE
# ==========================================================
def power_law(df):

    df = df.copy()

    genesis = pd.Timestamp("2009-01-03")

    dt = pd.to_datetime(df["Datetime"])

    df["Days"] = (dt.astype("int64") - genesis.value) / 86400e9

    df = df[df["Days"] > 0]

    if len(df) < 30:
        df["PowerLaw"] = np.nan
        return df

    x = np.log10(df["Days"].values)
    y = np.log10(df["Close"].values)

    if len(x) == 0 or len(y) == 0:
        df["PowerLaw"] = np.nan
        return df

    slope, intercept = np.polyfit(x, y, 1)

    df["PowerLaw"] = 10 ** (intercept + slope * x)

    return df


df = power_law(df)

# ==========================================================
# FEATURES
# ==========================================================
df["EMA169"] = ema(df["Close"], 169)
df["RSI"] = rsi(df["Close"], 14)

df = df.dropna()

if len(df) < 50:
    st.error("Dados insuficientes após indicadores")
    st.stop()

# ==========================================================
# STATE
# ==========================================================
price = float(df["Close"].iloc[-1])
ema169 = float(df["EMA169"].iloc[-1])
rsi_now = float(df["RSI"].iloc[-1])
pl = float(df["PowerLaw"].iloc[-1])

trend_ok = price > ema169

# ==========================================================
# SCORE
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((45 - rsi_now) * 1.5, 0, 30)
quality_score = 10 if rsi_now < 50 else 5

score = trend_score + momentum_score + quality_score

# ==========================================================
# SIGNAL
# ==========================================================
if not trend_ok:
    state = "BLOCKED"
    signal = "⛔ ABAIXO DA EMA 169"

elif score >= 75:
    state = "LONG"
    signal = "🟢 SETUP CONFIRMADO"

elif score >= 50:
    state = "WAIT"
    signal = "🟡 AGUARDAR"

else:
    state = "NO_TRADE"
    signal = "🔴 SEM EDGE"

# =========================================================
