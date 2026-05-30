import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from scipy.stats import percentileofscore
from datetime import datetime

st.set_page_config(
    page_title="Bitcoin Power Law ATR Probability",
    layout="wide"
)

st.title("₿ Bitcoin Power Law + ATR Probability")

st.markdown("""
Este aplicativo calcula:

- Power Law do Bitcoin
- Distância atual da Power Law
- Percentil histórico
- ATR(14)
- Probabilidade de atingir alvos em ATR
- Expectativa Matemática (EV)
- Tempo médio até atingir alvo
""")

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

ATR_PERIOD = 14
SIMILAR_PERCENT = 0.10
MAX_FORWARD_DAYS = 90

# ==========================================================
# DOWNLOAD DOS DADOS
# ==========================================================

@st.cache_data(ttl=3600)
def load_data():

    btc = yf.download(
        "BTC-USD",
        start="2010-07-17",
        auto_adjust=True,
        progress=False
    )

    btc = btc.dropna()
    btc = btc.reset_index()

    # garante padrão consistente
    if "Date" not in btc.columns:
        btc = btc.rename(columns={"index": "Date"})

    return btc


df = load_data()

# ==========================================================
# ATR
# ==========================================================

def calculate_atr(data, period=14):

    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    return atr


df["ATR"] = calculate_atr(df, ATR_PERIOD)

# ==========================================================
# POWER LAW
# ==========================================================

df = df.copy()
df["Date"] = pd.to_datetime(df["Date"])

genesis = pd.Timestamp("2009-01-03")
df["Days"] = (df["Date"] - genesis).dt.days.astype(float)

df = df[df["Days"] > 0].copy()

x = df["Days"].to_numpy().astype(float)
y = df["Close"].to_numpy().astype(float)

log_x = np.log10(x)
log_y = np.log10(y)

slope, intercept = np.polyfit(log_x, log_y, 1)

power_law = 10 ** (intercept + slope * log_x)

df["PowerLaw"] = np.asarray(power_law, dtype=float).flatten()

# ==========================================================
# DISTÂNCIA POWER LAW
# ==========================================================

df["PL_Distance"] = ((df["Close"] / df["PowerLaw"]) - 1) * 100

# ==========================================================
# 🔥 ESTADO ATUAL (CORREÇÃO PRINCIPAL)
# ==========================================================

current_price = float(df["Close"].iloc[-1])
current_powerlaw = float(df["PowerLaw"].iloc[-1])
current_distance = float(df["PL_Distance"].iloc[-1])
current_atr = float(df["ATR"].iloc[-1])

# ==========================================================
# PERCENTIL
# ==========================================================

distance_series = df["PL_Distance"].dropna()

current_percentile = percentileofscore(
    distance_series,
    current_distance
)

# ==========================================================
# RESUMO ATUAL
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Preço BTC", f"US$ {current_price:,.2f}")

with col2:
    st.metric("Power Law", f"US$ {current_powerlaw:,.2f}")

with col3:
    st.metric("Distância", f"{current_distance:.2f}%")

with col4:
    st.metric("Percentil", f"{current_percentile:.1f}")

st.divider()

# ==========================================================
# SIMILARIDADE
# ==========================================================

historical = df.iloc[:-1].copy()

historical["Similarity"] = (historical["PL_Distance"] - current_distance).abs()

sample_size = max(50, int(len(historical) * SIMILAR_PERCENT))

similar_days = historical.nsmallest(sample_size, "Similarity").copy()

# ==========================================================
# GRÁFICO
# ==========================================================

fig = go.Figure()

fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], name="BTC"))
fig.add_trace(go.Scatter(x=df["Date"], y=df["PowerLaw"], name="Power Law"))

fig.update_layout(height=600, yaxis_type="log")

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ==========================================================
# SIMULAÇÃO ATR
# ==========================================================

def simulate_path(data, start_index, atr_mult, max_days=90):

    start_price = data.iloc[start_index]["Close"]
    atr = data.iloc[start_index]["ATR"]

    if np.isnan(atr) or atr == 0:
        return None

    target_up = start_price + (atr * atr_mult)
    target_down = start_price - atr

    end_index = min(start_index + max_days, len(data) - 1)

    for i in range(start_index + 1, end_index):

        high = data.iloc[i]["High"]
        low = data.iloc[i]["Low"]

        if high >= target_up:
            return {"result": "win", "days": i - start_index}

        if low <= target_down:
            return {"result": "loss", "days": i - start_index}

    return None

# ==========================================================
# ENGINE
# ==========================================================

def run_probability_engine(similar_data, full_data):

    results = {}

    for atr_mult in [1, 2, 3, 4]:

        wins = 0
        losses = 0
        times = []

        for idx in similar_data.index:

            idx_full = full_data.index.get_loc(idx)

            sim = simulate_path(full_data, idx_full, atr_mult)

            if sim is None:
                continue

            if sim["result"] == "win":
                wins += 1
            else:
                losses += 1

            times.append(sim["days"])

        total = wins + losses

        if total == 0:
            results[atr_mult] = {"win_rate": 0, "ev": 0, "avg_time": 0, "samples": 0}
            continue

        win_rate = wins / total
        loss_rate = losses / total

        ev = (win_rate * atr_mult) - (loss_rate * 1)
        avg_time = np.mean(times)

        results[atr_mult] = {
            "win_rate": win_rate,
            "ev": ev,
            "avg_time": avg_time,
            "samples": total
        }

    return results

# ==========================================================
# EXECUÇÃO
# ==========================================================

st.subheader("Probabilidade ATR")

results = run_probability_engine(similar_days, df)

table_data = []

for k, v in results.items():
    table_data.append([
        f"+{k} ATR",
        f"{v['win_rate']*100:.2f}%",
        f"{v['ev']:.3f}",
        f"{v['avg_time']:.1f}",
        v["samples"]
    ])

table_df = pd.DataFrame(table_data, columns=[
    "Cenário", "Win Rate", "EV", "Tempo", "Amostras"
])

st.dataframe(table_df, use_container_width=True)

# ==========================================================
# MELHOR EV
# ==========================================================

best = max(results.items(), key=lambda x: x[1]["ev"])

st.success(f"Melhor EV: +{best[0]} ATR = {best[1]['ev']:.3f}")

# ==========================================================
# SCORE FINAL
# ==========================================================

ev_values = [v["ev"] for v in results.values()]
ev_mean = np.mean(ev_values)

final_score = min(max(ev_mean * 25, 0), 100)

st.metric("Score Final", f"{final_score:.1f}/100")

if final_score >= 75:
    st.success("🟢 BUY ZONE")
elif final_score >= 50:
    st.warning("🟡 NEUTRO")
else:
    st.error("🔴 EVITAR")
