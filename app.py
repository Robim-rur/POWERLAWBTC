import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Institutional Engine", layout="wide")
st.title("🏦 BTC Institutional Signal Engine (FULL VERSION)")

tz = ZoneInfo("America/Sao_Paulo")

# ==========================================================
# SESSION STATE
# ==========================================================
if "log" not in st.session_state:
    st.session_state.log = []

# ==========================================================
# DATA (STABLE REAL-TIME VIA POLLING)
# ==========================================================
@st.cache_data(ttl=10)
def load_data():
    df = yf.download(
        "BTC-USD",
        period="7d",
        interval="5m",
        auto_adjust=True,
        progress=False
    )

    df = df.reset_index()
    df["Datetime"] = pd.to_datetime(df["Datetime"])

    return df


df = load_data()

# ==========================================================
# POWER LAW
# ==========================================================
def power_law(df):
    df = df.copy()

    genesis = pd.Timestamp("2009-01-03")
    df["Days"] = (df["Datetime"] - genesis).dt.days.astype(float)
    df = df[df["Days"] > 0]

    x = np.log10(df["Days"].values)
    y = np.log10(df["Close"].values)

    slope, intercept = np.polyfit(x, y, 1)

    df["PowerLaw"] = 10 ** (intercept + slope * x)

    return df


df = power_law(df)

# ==========================================================
# INDICATORS
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


df["EMA169"] = ema(df["Close"], 169)
df["RSI"] = rsi(df["Close"], 14)

df = df.dropna()

# ==========================================================
# STATE
# ==========================================================
price = float(df["Close"].iloc[-1])
ema169 = float(df["EMA169"].iloc[-1])
rsi_now = float(df["RSI"].iloc[-1])
pl = float(df["PowerLaw"].iloc[-1])

trend_ok = price > ema169

# ==========================================================
# SCORE ENGINE
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((40 - rsi_now) * 1.5, 0, 25)
quality_score = 15 if rsi_now < 45 else 5 if rsi_now < 55 else 0

score = trend_score + momentum_score + quality_score

# ==========================================================
# SIGNAL ENGINE
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
    signal = "🔴 SEM SETUP"

# ==========================================================
# LOG (TIME CORRIGIDO)
# ==========================================================
entry = {
    "time": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"),
    "price": price,
    "ema169": ema169,
    "rsi": rsi_now,
    "score": score,
    "state": state
}

if len(st.session_state.log) == 0 or st.session_state.log[-1]["state"] != state:
    st.session_state.log.append(entry)

# ==========================================================
# UI
# ==========================================================
if state == "LONG":
    st.success(signal)
elif state == "WAIT":
    st.warning(signal)
else:
    st.error(signal)

# ==========================================================
# METRICS
# ==========================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("BTC", f"${price:,.0f}")
c2.metric("EMA 169", f"${ema169:,.0f}")
c3.metric("Power Law", f"${pl:,.0f}")
c4.metric("Score", f"{score:.1f}/100")

# ==========================================================
# CHART
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(x=df["Datetime"], y=df["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=df["Datetime"], y=df["EMA169"], name="EMA 169"))

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["PowerLaw"],
    name="Power Law",
    line=dict(dash="dot")
))

fig.update_layout(height=650)

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# LOG
# ==========================================================
st.subheader("Log de Sinais")

st.dataframe(pd.DataFrame(st.session_state.log))

# ==========================================================
# SUMMARY
# ==========================================================
st.write({
    "price": price,
    "ema169": ema169,
    "rsi": rsi_now,
    "score": score,
    "state": state
})
