import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Signal Engine Pro", layout="wide")
st.title("🏦 BTC Institutional Signal Engine PRO")

# ==========================================================
# DATA
# ==========================================================
@st.cache_data(ttl=3600)
def load_data():
    df = yf.download(
        "BTC-USD",
        start="2010-07-17",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    return df


df = load_data()

if df.empty:
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


df["EMA169"] = ema(df["Close"], 169)
df["RSI"] = rsi(df["Close"], 14)
df = df.dropna()

# ==========================================================
# STATE
# ==========================================================
price = df["Close"].iloc[-1]
ema = df["EMA169"].iloc[-1]
rsi_now = df["RSI"].iloc[-1]

# ==========================================================
# SCORE (ESTÁVEL 0–100)
# ==========================================================
trend_score = 60 if price > ema else 0
momentum_score = np.clip((40 - rsi_now) * 1.5, 0, 25)
quality_score = 15 if rsi_now < 45 else 5 if rsi_now < 55 else 0

score = trend_score + momentum_score + quality_score

# ==========================================================
# SIGNAL STATE MACHINE (PROFISSIONAL)
# ==========================================================
if price < ema:
    state = "BLOCKED"
    message = "⛔ BLOQUEADO (ABAIXO DA EMA 169)"

elif score >= 75:
    state = "LONG"
    message = "🟢 LONG SETUP CONFIRMADO"

elif score >= 50:
    state = "WAIT"
    message = "🟡 AGUARDAR CONFIRMAÇÃO"

else:
    state = "NO_TRADE"
    message = "🔴 SEM TRADE"

# ==========================================================
# UI RENDERER (SEM BUG STREAMLIT)
# ==========================================================
if state == "LONG":
    st.success(message)

elif state == "WAIT":
    st.warning(message)

elif state == "BLOCKED":
    st.error(message)

else:
    st.error(message)

# ==========================================================
# METRICS
# ==========================================================
c1, c2, c3 = st.columns(3)

c1.metric("BTC", f"${price:,.0f}")
c2.metric("EMA 169", f"${ema:,.0f}")
c3.metric("Score", f"{score:.1f}/100")

st.divider()

# ==========================================================
# CHART
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA169"], name="EMA 169"))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# SUMMARY
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price,
    "EMA169": ema,
    "RSI": rsi_now,
    "Score": score,
    "State": state
})
