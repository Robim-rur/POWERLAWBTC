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
st.title("🏦 BTC Power Law + Multi-Timeframe Institutional Engine")

ATR_PERIOD = 14

# ==========================================================
# DATA
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
# INDICADORES BASE
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

# ==========================================================
# POWER LAW
# ==========================================================
def power_law(df):

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    genesis = pd.Timestamp("2009-01-03")
    df["Days"] = (df["Date"] - genesis).dt.days.astype(float)
    df = df[df["Days"] > 0]

    x = np.log10(df["Days"].to_numpy())
    y = np.log10(df["Close"].to_numpy())

    slope, intercept = np.polyfit(x, y, 1)
    df["PowerLaw"] = 10 ** (intercept + slope * x)

    df["PL_Distance"] = ((df["Close"] / df["PowerLaw"]) - 1) * 100

    return df


daily = power_law(daily)

# ==========================================================
# DAILY INDICATORS
# ==========================================================
daily["EMA169"] = ema(daily["Close"], 169)
daily["RSI"] = rsi(daily["Close"], 14)

daily = daily.dropna()

price_d = daily["Close"].iloc[-1]
ema_d = daily["EMA169"].iloc[-1]
rsi_d = daily["RSI"].iloc[-1]

# ==========================================================
# 4H INDICATORS
# ==========================================================
h4["RSI"] = rsi(h4["Close"], 14)
h4 = h4.dropna()

rsi_h = h4["RSI"].iloc[-1]
price_h = h4["Close"].iloc[-1]

# ==========================================================
# MULTI-TF LOGIC
# ==========================================================
trend_strength = price_d / ema_d

trend_score = np.clip((trend_strength - 0.95) * 200, 0, 60)
momentum_score = np.clip((40 - rsi_h) * 0.6, 0, 25)
alignment_score = 15 if rsi_h < 45 and rsi_d < 50 else 5

score = trend_score + momentum_score + alignment_score

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if trend_strength < 1:
    signal = "🔴 BLOQUEADO (ABAIXO DA EMA 169)"
elif score > 75:
    signal = "🟢 LONG SETUP CONFIRMADO"
elif score > 50:
    signal = "🟡 AGUARDAR CONFIRMAÇÃO"
else:
    signal = "🔴 SEM TRADE"

# ==========================================================
# DISPLAY
# ==========================================================
c1, c2, c3 = st.columns(3)

c1.metric("BTC", f"${price_d:,.0f}")
c2.metric("EMA 169", f"${ema_d:,.0f}")
c3.metric("Score", f"{score:.1f}/100")

st.divider()

st.success(signal) if "CONFIRMADO" in signal else st.warning(signal) if "AGUARDAR" in signal else st.error(signal)

# ==========================================================
# CHART (COMPLETO)
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(x=daily["Date"], y=daily["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=daily["Date"], y=daily["EMA169"], name="EMA 169"))
fig.add_trace(go.Scatter(x=daily["Date"], y=daily["PowerLaw"], name="Power Law"))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# SUMMARY
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price_d,
    "EMA169": ema_d,
    "RSI Diário": rsi_d,
    "RSI 4H": rsi_h,
    "Score": score,
    "Trend Strength": trend_strength,
    "Signal": signal
})
