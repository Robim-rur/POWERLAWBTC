import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Signal Engine v2", layout="wide")
st.title("🏦 BTC Signal Engine v2 — Institutional Grade")

# ==========================================================
# SESSION STATE (HISTÓRICO DE SINAIS)
# ==========================================================
if "signal_log" not in st.session_state:
    st.session_state.signal_log = []

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
    st.error("Sem dados disponíveis")
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
# STATE (ÚLTIMO CANDLE)
# ==========================================================
price = df["Close"].iloc[-1]
ema169 = df["EMA169"].iloc[-1]
rsi_now = df["RSI"].iloc[-1]

trend_ok = price > ema169

# ==========================================================
# SCORE (CONTÍNUO E ESTÁVEL)
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((40 - rsi_now) * 1.5, 0, 25)
quality_score = 15 if rsi_now < 45 else 5 if rsi_now < 55 else 0

score = trend_score + momentum_score + quality_score

# ==========================================================
# STATE MACHINE (PROFISSIONAL)
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
# LOG DE SINAL (HISTÓRICO)
# ==========================================================
last_entry = st.session_state.signal_log[-1] if st.session_state.signal_log else None

new_entry = {
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "price": float(price),
    "ema169": float(ema169),
    "rsi": float(rsi_now),
    "score": float(score),
    "state": state,
    "signal": signal
}

# evita duplicação idêntica consecutiva
if last_entry is None or last_entry["state"] != state:
    st.session_state.signal_log.append(new_entry)

# ==========================================================
# UI RENDERER (SEM BUG STREAMLIT)
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

c1.metric("BTC", f"${price:,.0f}")
c2.metric("EMA 169", f"${ema169:,.0f}")
c3.metric("Score", f"{score:.1f}/100")

st.divider()

# ==========================================================
# CHART
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["Close"],
    name="BTC"
))

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["EMA169"],
    name="EMA 169"
))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# HISTÓRICO DE SINAIS
# ==========================================================
st.subheader("📊 Histórico de Sinais (Engine Log)")

log_df = pd.DataFrame(st.session_state.signal_log)

if not log_df.empty:
    st.dataframe(log_df, use_container_width=True)

    st.download_button(
        "📥 Baixar histórico",
        log_df.to_csv(index=False),
        file_name="signal_log.csv",
        mime="text/csv"
    )
else:
    st.info("Ainda não há histórico de sinais.")

# ==========================================================
# RESUMO
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price,
    "EMA169": ema169,
    "RSI": rsi_now,
    "Score": score,
    "State": state
})
