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
st.set_page_config(page_title="BTC Real-Time Engine PRO", layout="wide")
st.title("🏦 BTC Real-Time Engine PRO (Institutional)")

tz = ZoneInfo("America/Sao_Paulo")

# 🔁 auto refresh (tempo real simulado)
st.autorefresh(interval=60 * 1000, key="refresh")  # 60s

# ==========================================================
# SESSION STATE
# ==========================================================
if "signal_log" not in st.session_state:
    st.session_state.signal_log = []

# ==========================================================
# DATA
# ==========================================================
@st.cache_data(ttl=60)
def load_data():

    df = yf.download(
        "BTC-USD",
        period="30d",
        interval="1h",   # 🔥 agora é base de 1 hora (mais real-time)
        auto_adjust=True,
        progress=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    # ======================================================
    # 🔥 FIX DEFINITIVO DE FUSO HORÁRIO
    # ======================================================
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
    df["Datetime"] = df["Datetime"].dt.tz_convert("America/Sao_Paulo")
    df["Datetime"] = df["Datetime"].dt.tz_localize(None)

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
price = float(df["Close"].iloc[-1])
ema169 = float(df["EMA169"].iloc[-1])
rsi_now = float(df["RSI"].iloc[-1])

trend_ok = price > ema169

# ==========================================================
# SCORE ENGINE
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((40 - rsi_now) * 1.5, 0, 25)
quality_score = 15 if rsi_now < 45 else 5 if rsi_now < 55 else 0

score = trend_score + momentum_score + quality_score

# ==========================================================
# STATE MACHINE
# ==========================================================
if not trend_ok:
    state = "BLOCKED"
    signal = "⛔ BLOQUEADO (ABAIXO DA EMA 169)"

elif score >= 75:
    state = "LONG"
    signal = "🟢 LONG SETUP CONFIRMADO"

elif score >= 50:
    state = "WAIT"
    signal = "🟡 AGUARDAR CONFIRMAÇÃO"

else:
    state = "NO_TRADE"
    signal = "🔴 SEM TRADE"

# ==========================================================
# LOG (TIME CORRIGIDO)
# ==========================================================
last_state = st.session_state.signal_log[-1]["state"] if st.session_state.signal_log else None

entry = {
    "time": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"),
    "price": price,
    "ema169": ema169,
    "rsi": rsi_now,
    "score": score,
    "state": state,
    "signal": signal
}

if last_state != state:
    st.session_state.signal_log.append(entry)

# ==========================================================
# UI SIGNAL (SEGURO)
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
c1, c2, c3 = st.columns(3)

c1.metric("BTC (1H)", f"${price:,.0f}")
c2.metric("EMA 169", f"${ema169:,.0f}")
c3.metric("Score", f"{score:.1f}/100")

st.divider()

# ==========================================================
# CHART REAL-TIME
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["Close"],
    name="BTC (1H)"
))

fig.add_trace(go.Scatter(
    x=df["Datetime"],
    y=df["EMA169"],
    name="EMA 169"
))

fig.update_layout(height=650)

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# HISTÓRICO
# ==========================================================
st.subheader("📊 Histórico de Sinais (Real-Time)")

log_df = pd.DataFrame(st.session_state.signal_log)

if not log_df.empty:
    st.dataframe(log_df, use_container_width=True)
else:
    st.info("Sem histórico ainda.")

# ==========================================================
# RESUMO
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price,
    "EMA169": ema169,
    "RSI": rsi_now,
    "Score": score,
    "State": state,
    "Timeframe": "1H Real-Time Simulado",
    "Timezone": "America/Sao_Paulo"
})
