import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from scipy.stats import percentileofscore

# ==========================================================
# APP CONFIG
# ==========================================================
st.set_page_config(
    page_title="BTC Power Law Hedge Fund Model",
    layout="wide"
)

st.title("🏦 Bitcoin Power Law — Hedge Fund Engine")

# ==========================================================
# PARAMETERS
# ==========================================================
ATR_PERIOD = 14
SIMILARITY_SAMPLE = 0.10
MC_SIMULATIONS = 200
MAX_DAYS = 90

# ==========================================================
# DATA ENGINE (BULLETPROOF)
# ==========================================================
@st.cache_data(ttl=3600)
def load_data():

    df = yf.download(
        "BTC-USD",
        start="2010-07-17",
        auto_adjust=True,
        progress=False
    )

    if df is None or len(df) == 0:
        return pd.DataFrame()

    df = df.copy()

    # flatten multiindex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)

    if "Date" not in df.columns:
        df.rename(columns={df.columns[0]: "Date"}, inplace=True)

    return df


df = load_data()

if df.empty:
    st.error("No data loaded")
    st.stop()

# ==========================================================
# ATR ENGINE
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


df["ATR"] = atr(df, ATR_PERIOD)
df = df.dropna().reset_index(drop=True)

# ==========================================================
# POWER LAW MODEL (LOG REGRESSION)
# ==========================================================
df["Date"] = pd.to_datetime(df["Date"])

genesis = pd.Timestamp("2009-01-03")
df["Days"] = (df["Date"] - genesis).dt.days.astype(float)

df = df[df["Days"] > 0].copy()

x = np.log10(df["Days"].to_numpy(dtype=float))
y = np.log10(df["Close"].to_numpy(dtype=float))

slope, intercept = np.polyfit(x, y, 1)

df["PowerLaw"] = 10 ** (intercept + slope * x)

# ==========================================================
# SAFE NUMPY FEATURES
# ==========================================================
close = df["Close"].to_numpy(dtype=float)
pl = df["PowerLaw"].to_numpy(dtype=float)

df["PL_Distance"] = ((close / pl) - 1.0) * 100

# ==========================================================
# CURRENT STATE
# ==========================================================
current_price = close[-1]
current_pl = pl[-1]
current_distance = df["PL_Distance"].iloc[-1]
current_atr = df["ATR"].iloc[-1]

current_percentile = percentileofscore(
    df["PL_Distance"],
    current_distance
)

# ==========================================================
# DISPLAY METRICS
# ==========================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("BTC", f"${current_price:,.0f}")
c2.metric("Power Law", f"${current_pl:,.0f}")
c3.metric("Distance", f"{current_distance:.2f}%")
c4.metric("Percentile", f"{current_percentile:.1f}")

st.divider()

# ==========================================================
# REGIME FILTER (INSTITUTIONAL LOGIC)
# ==========================================================
def regime(distance):

    if distance < -25:
        return "DEEP VALUE ZONE"
    elif distance < 0:
        return "BELOW FAIR VALUE"
    elif distance < 25:
        return "FAIR VALUE"
    else:
        return "OVEREXTENDED"


regime_state = regime(current_distance)

st.subheader(f"Market Regime: {regime_state}")

# ==========================================================
# SIMILARITY ENGINE (VECTOR APPROACH)
# ==========================================================
hist = df.iloc[:-1].copy()

hist["sim"] = np.abs(hist["PL_Distance"] - current_distance)

sample_size = max(50, int(len(hist) * SIMILARITY_SAMPLE))

similar = hist.nsmallest(sample_size, "sim")

# ==========================================================
# MONTE CARLO ENGINE (REAL EDGE SIMULATION)
# ==========================================================
def monte_carlo(df, start_idx, atr_mult=2):

    start_price = df.iloc[start_idx]["Close"]
    atr_val = df.iloc[start_idx]["ATR"]

    if atr_val <= 0:
        return None

    win = 0

    for _ in range(MC_SIMULATIONS):

        price = start_price

        for i in range(MAX_DAYS):

            shock = np.random.normal(0, atr_val * 0.5)
            price += shock

            if price >= start_price + atr_val * atr_mult:
                win += 1
                break

            if price <= start_price - atr_val:
                break

    return win / MC_SIMULATIONS


# ==========================================================
# BACKTEST ENGINE
# ==========================================================
def engine(similar, df):

    results = {}

    for mult in [1, 2, 3, 4]:

        probs = []

        for idx in similar.index:

            pos = df.index.get_loc(idx)

            p = monte_carlo(df, pos, mult)

            if p is not None:
                probs.append(p)

        if len(probs) == 0:
            continue

        results[mult] = {
            "prob": np.mean(probs),
            "ev": np.mean(probs) * mult - (1 - np.mean(probs)),
            "samples": len(probs)
        }

    return results


results = engine(similar, df)

best = max(results.items(), key=lambda x: x[1]["ev"])

st.success(f"Best: +{best[0]} ATR | EV {best[1]['ev']:.3f}")

# ==========================================================
# SCORE SYSTEM (INSTITUTIONAL)
# ==========================================================
ev_mean = np.mean([r["ev"] for r in results.values()])

score = (
    min(max(ev_mean * 30, 0), 100) * 0.5 +
    max(0, 100 - abs(current_distance)) * 0.3 +
    max(0, 100 - current_percentile) * 0.2
)

st.metric("Hedge Fund Score", f"{score:.1f}/100")

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if score > 75 and ev_mean > 0:
    st.success("🟢 INSTITUTIONAL BUY ZONE")
elif score > 50:
    st.warning("🟡 NEUTRAL RISK")
else:
    st.error("🔴 RISK OFF")

# ==========================================================
# CHARTS
# ==========================================================
fig = go.Figure()

fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=df["Date"], y=df["PowerLaw"], name="Power Law"))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# FINAL SUMMARY
# ==========================================================
st.subheader("Institutional Summary")

st.write({
    "Price": current_price,
    "Power Law": current_pl,
    "Distance": current_distance,
    "Regime": regime_state,
    "Score": score
})
