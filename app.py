import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Multi-Timeframe Engine", layout="wide")
st.title("🏦 BTC Institutional Engine (Power Law FIX)")

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

if daily.empty:
    st.error("Sem dados")
    st.stop()

# ==========================================================
# POWER LAW (RESTAURADO CORRETAMENTE)
# ==========================================================
def power_law(df):

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"])
    genesis = pd.Timestamp("2009-01-03")

    df["Days"] = (df["Date"] - genesis).dt.days.astype(float)
    df = df[df["Days"] > 0].copy()

    x = np.log10(df["Days"].to_numpy())
    y = np.log10(df["Close"].to_numpy())

    slope, intercept = np.polyfit(x, y, 1)

    df["PowerLaw"] = 10 ** (intercept + slope * x)

    df["PL_Distance"] = ((df["Close"] / df["PowerLaw"]) - 1) * 100

    return df


daily = power_law(daily)

# ==========================================================
# INDICADORES
# ==========================================================
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()


def rsi(s, p=14):
    d = s.diff()
    up = np.where(d > 0, d, 0)
    dn = np.where(d < 0, -d, 0)

    au = pd.Series(up).rolling(p).mean()
    ad = pd.Series(dn).rolling(p).mean()

    rs = au / ad
    return 100 - (100 / (1 + rs))


daily["EMA169"] = ema(daily["Close"], 169)
daily["RSI"] = rsi(daily["Close"], 14)

h4["RSI"] = rsi(h4["Close"], 14)

daily = daily.dropna()
h4 = h4.dropna()

# ==========================================================
# STATE
# ==========================================================
price = daily["Close"].iloc[-1]
ema169 = daily["EMA169"].iloc[-1]
pl = daily["PowerLaw"].iloc[-1]

rsi_d = daily["RSI"].iloc[-1]
rsi_h = h4["RSI"].iloc[-1]

trend_ok = price > ema169

# ==========================================================
# SCORE SIMPLES E ESTÁVEL
# ==========================================================
trend_score = 60 if trend_ok else 0
momentum_score = np.clip((40 - rsi_h) * 0.6, 0, 25)
alignment_score = 15 if rsi_d < 50 and rsi_h < 45 else 5

score = trend_score + momentum_score + alignment_score

# ==========================================================
# SIGNAL
# ==========================================================
if not trend_ok:
    signal = "🔴 BLOQUEADO (ABAIXO DA EMA 169)"
elif score > 75:
    signal = "🟢 LONG SETUP CONFIRMADO"
elif score > 50:
    signal = "🟡 AGUARDAR CONFIRMAÇÃO"
else:
    signal = "🔴 SEM TRADE"

# ==========================================================
# UI
# ==========================================================
c1, c2, c3 = st.columns(3)

c1.metric("BTC", f"${price:,.0f}")
c2.metric("EMA 169", f"${ema169:,.0f}")
c3.metric("Score", f"{score:.1f}/100")

st.divider()

st.success(signal) if "CONFIRMADO" in signal else st.warning(signal) if "AGUARDAR" in signal else st.error(signal)

# ==========================================================
# CHART (POWER LAW RESTAURADO)
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=daily["Date"],
    y=daily["Close"],
    name="BTC"
))

fig.add_trace(go.Scatter(
    x=daily["Date"],
    y=daily["EMA169"],
    name="EMA 169"
))

fig.add_trace(go.Scatter(
    x=daily["Date"],
    y=daily["PowerLaw"],
    name="Power Law",
    line=dict(dash="dot", width=2)
))

fig.update_layout(height=650, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# SUMMARY
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price,
    "EMA169": ema169,
    "Power Law": pl,
    "RSI Diário": rsi_d,
    "RSI 4H": rsi_h,
    "Score": score,
    "Trend": trend_ok
})
