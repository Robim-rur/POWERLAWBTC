import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="Hedge Fund BTC Engine", layout="wide")
st.title("🏦 BTC Hedge Fund Data Engine — Blinded Version")

# ==========================================================
# STATE
# ==========================================================
if "log" not in st.session_state:
    st.session_state.log = []

# ==========================================================
# SAFE DATA ENGINE (HEDGE FUND STYLE)
# ==========================================================
def fetch_yahoo(interval="1h", period="30d"):

    df = yf.download(
        "BTC-USD",
        interval=interval,
        period=period,
        auto_adjust=True,
        progress=False
    )

    if df is None or len(df) == 0:
        return pd.DataFrame()

    df = df.reset_index()

    # normalização robusta de tempo
    time_col = df.columns[0]
    df.rename(columns={time_col: "Datetime"}, inplace=True)

    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")

    # força colunas numéricas
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    # garante array 1D estável
    df["Close"] = df["Close"].values.reshape(-1)

    return df


df = fetch_yahoo(interval="1h", period="60d")

if df.empty:
    st.error("Sem dados — Yahoo falhou")
    st.stop()

# ==========================================================
# EMA (ROBUSTA)
# ==========================================================
def ema(series, period):
    return pd.Series(series).ewm(span=period, adjust=False).mean()

# ==========================================================
# RSI (WILDER STYLE SAFE)
# ==========================================================
def rsi(series, period=14):

    series = np.asarray(series).reshape(-1)

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
# POWER LAW (BLINDADO)
# ==========================================================
def power_law(df):

    df = df.copy()

    genesis = pd.Timestamp("2009-01-03")

    dt = pd.to_datetime(df["Datetime"])

    df["Days"] = (dt.astype("int64") - genesis.value) / 86400e9

    df = df.dropna(subset=["Days", "Close"])
    df = df[df["Days"] > 0]

    # proteção hedge fund
    if len(df) < 20:
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
# INDICATORS
# ==========================================================
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
# SCORE (INSTITUTIONAL STYLE)
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((45 - rsi_now) * 1.5, 0, 30)
quality_score = 10 if rsi_now < 50 else 5

score = trend_score + momentum_score + quality_score

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if not trend_ok:
    state = "BLOCKED"
    signal = "⛔ ABAIXO DA EMA 169"

elif score >= 75:
    state = "LONG"
    signal = "🟢 SETUP INSTITUCIONAL CONFIRMADO"

elif score >= 50:
    state = "WAIT"
    signal = "🟡 AGUARDAR CONFIRMAÇÃO"

else:
    state = "NO_TRADE"
    signal = "🔴 SEM EDGE"

# ==========================================================
# LOG
# ==========================================================
st.session_state.log.append({
    "time": datetime.now().strftime("%H:%M:%S"),
    "price": price,
    "ema169": ema169,
    "rsi": rsi_now,
    "score": score,
    "state": state
})

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
c3.metric("RSI 14", f"{rsi_now:.2f}")
c4.metric("Score", f"{score:.1f}/100")

# ==========================================================
# CHART
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["Close"],
    name="BTC"
))

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["EMA169"],
    name="EMA 169"
))

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["PowerLaw"],
    name="Power Law",
    line=dict(dash="dot")
))

fig.update_layout(height=650)

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# LOG TABLE
# ==========================================================
st.subheader("Log Institucional")

st.dataframe(pd.DataFrame(st.session_state.log))
