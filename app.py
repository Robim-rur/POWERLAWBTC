import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from scipy.stats import percentileofscore

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC Institutional Engine", layout="wide")
st.title("🏦 BTC Power Law + Swing Trade Institutional Engine")

ATR_PERIOD = 14
MC_SIMULATIONS = 200
MAX_DAYS = 90
SIMILARITY_SAMPLE = 0.10

# ==========================================================
# DATA
# ==========================================================
@st.cache_data(ttl=3600)
def load_data():
    df = yf.download("BTC-USD", start="2010-07-17", auto_adjust=True, progress=False)

    if df is None or len(df) == 0:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    df.rename(columns={df.columns[0]: "Date"}, inplace=True)

    return df


df = load_data()

if df.empty:
    st.error("Sem dados")
    st.stop()

# ==========================================================
# INDICADORES BASE
# ==========================================================
def atr(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    return tr.rolling(period).mean()


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
    d_line = k_line.rolling(d).mean()

    return k_line, d_line


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
    adx_val = dx.rolling(period).mean()

    return adx_val, plus_di, minus_di


# ==========================================================
# APPLY INDICATORS
# ==========================================================
df["ATR"] = atr(df, ATR_PERIOD)
df["EMA69"] = ema(df["Close"], 69)
df["RSI"] = rsi(df["Close"], 14)

df["STOCH_K"], df["STOCH_D"] = stochastic_rsi(df["RSI"])
df["ADX"], df["DI+"], df["DI-"] = adx(df)

df["VOL_MA20"] = df["Volume"].rolling(20).mean()

df = df.dropna().reset_index(drop=True)

# ==========================================================
# POWER LAW
# ==========================================================
df["Date"] = pd.to_datetime(df["Date"])
genesis = pd.Timestamp("2009-01-03")

df["Days"] = (df["Date"] - genesis).dt.days.astype(float)
df = df[df["Days"] > 0].copy()

x = np.log10(df["Days"].to_numpy())
y = np.log10(df["Close"].to_numpy())

slope, intercept = np.polyfit(x, y, 1)

df["PowerLaw"] = 10 ** (intercept + slope * x)

df["PL_Distance"] = ((df["Close"] / df["PowerLaw"]) - 1) * 100

# ==========================================================
# CURRENT STATE
# ==========================================================
price = df["Close"].iloc[-1]
pl = df["PowerLaw"].iloc[-1]
dist = df["PL_Distance"].iloc[-1]
rsi_now = df["RSI"].iloc[-1]
stoch_k = df["STOCH_K"].iloc[-1]
adx_now = df["ADX"].iloc[-1]
di_plus = df["DI+"].iloc[-1]
ema69 = df["EMA69"].iloc[-1]
vol = df["Volume"].iloc[-1]
vol_ma = df["VOL_MA20"].iloc[-1]

percentile = percentileofscore(df["PL_Distance"], dist)

# ==========================================================
# REGIME
# ==========================================================
def regime(dist):
    if dist < -25:
        return "DEEP VALUE ZONE"
    elif dist < 0:
        return "BELOW FAIR VALUE"
    elif dist < 25:
        return "FAIR VALUE"
    return "OVEREXTENDED"


reg = regime(dist)

# ==========================================================
# SCORE (INSTITUTIONAL VERSION)
# ==========================================================
trend_score = 1 if price > ema69 and adx_now > 20 and di_plus > df["DI-"].iloc[-1] else 0

momentum_score = 1 if (rsi_now < 40 and stoch_k < 0.2) else 0

value_score = max(0, 1 - abs(dist) / 100)

volume_score = 1 if vol > vol_ma else 0

score = (
    trend_score * 35 +
    momentum_score * 25 +
    value_score * 25 +
    volume_score * 15
) * 100

# ==========================================================
# DISPLAY
# ==========================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("BTC", f"${price:,.0f}")
c2.metric("Power Law", f"${pl:,.0f}")
c3.metric("Distância", f"{dist:.2f}%")
c4.metric("Score", f"{score:.1f}/100")

st.divider()

st.subheader(f"Regime: {reg}")

# ==========================================================
# SIGNAL
# ==========================================================
if score > 75:
    st.success("🟢 LONG SETUP CONFIRMADO")
elif score > 50:
    st.warning("🟡 AGUARDAR CONFIRMAÇÃO")
else:
    st.error("🔴 SEM TRADE")

# ==========================================================
# CHART
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA69"], name="EMA 69"))
fig.add_trace(go.Scatter(x=df["Date"], y=df["PowerLaw"], name="Power Law"))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# SUMMARY
# ==========================================================
st.subheader("Resumo Institucional")

st.write({
    "Preço": price,
    "Power Law": pl,
    "Distância": dist,
    "RSI": rsi_now,
    "Stoch RSI K": stoch_k,
    "ADX": adx_now,
    "Regime": reg,
    "Score": score
})
