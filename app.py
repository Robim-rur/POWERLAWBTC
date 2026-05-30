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

    btc.reset_index(inplace=True)

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

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    return atr


df["ATR"] = calculate_atr(df, ATR_PERIOD)

# ==========================================================
# POWER LAW (VERSÃO FINAL - ZERO ERRO STREAMLIT)
# ==========================================================

df = df.copy()

df["Date"] = pd.to_datetime(df["Date"])

genesis = pd.Timestamp("2009-01-03")

df["Days"] = (df["Date"] - genesis).dt.days.astype(float)

df = df[df["Days"] > 0].copy()

x = df["Days"].to_numpy().reshape(-1).astype(float)
y = df["Close"].to_numpy().reshape(-1).astype(float)

log_x = np.log10(x).reshape(-1)
log_y = np.log10(y).reshape(-1)

slope, intercept = np.polyfit(log_x, log_y, 1)

power_law = 10 ** (intercept + slope * log_x)

df["PowerLaw"] = np.asarray(power_law, dtype=float).flatten()

df["Close"] = df["Close"].astype(float)

# ==========================================================
# DISTÂNCIA DA POWER LAW
# ==========================================================

pl = df["PowerLaw"].to_numpy(dtype=float).flatten()
price = df["Close"].to_numpy(dtype=float).flatten()

df["PL_Distance"] = ((price / pl) - 1.0) * 100

# ==========================================================
# FIX: VARIÁVEIS FALTANTES (CRÍTICO)
# ==========================================================

current_price = float(df["Close"].iloc[-1])
current_powerlaw = float(df["PowerLaw"].iloc[-1])
current_distance = float(df["PL_Distance"].iloc[-1])
current_atr = float(df["ATR"].iloc[-1])

# ==========================================================
# PERCENTIL HISTÓRICO
# ==========================================================

distance_series = df["PL_Distance"].dropna()

current_percentile = percentileofscore(
    distance_series.values,
    current_distance
)

# ==========================================================
# RESUMO ATUAL
# ==========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Preço BTC",
        f"US$ {current_price:,.2f}"
    )

with col2:
    st.metric(
        "Power Law",
        f"US$ {current_powerlaw:,.2f}"
    )

with col3:
    st.metric(
        "Distância",
        f"{current_distance:.2f}%"
    )

with col4:
    st.metric(
        "Percentil",
        f"{current_percentile:.1f}"
    )

st.divider()

# ==========================================================
# ENCONTRAR DIAS SEMELHANTES
# ==========================================================

historical = df.iloc[:-1].copy()

historical["Similarity"] = (
    historical["PL_Distance"]
    - current_distance
).abs()

sample_size = max(
    50,
    int(len(historical) * SIMILAR_PERCENT)
)

similar_days = historical.nsmallest(
    sample_size,
    "Similarity"
).copy()

st.subheader("Amostra Histórica")

st.write(
    f"Dias analisados: {len(similar_days)}"
)

st.write(
    f"Distância atual da Power Law: "
    f"{current_distance:.2f}%"
)

# ==========================================================
# GRÁFICO POWER LAW
# ==========================================================

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df["Date"],
        y=df["Close"],
        name="BTC",
        mode="lines"
    )
)

fig.add_trace(
    go.Scatter(
        x=df["Date"],
        y=df["PowerLaw"],
        name="Power Law",
        mode="lines"
    )
)

fig.update_layout(
    height=600,
    yaxis_type="log",
    title="Bitcoin vs Power Law"
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ==========================================================
# FUNÇÃO: SIMULAÇÃO ATR
# ==========================================================

def simulate_path(data, start_index, atr_mult, max_days=90):

    start_price = data.iloc[start_index]["Close"]
    atr = data.iloc[start_index]["ATR"]

    if np.isnan(atr) or atr == 0:
        return None

    target_up = start_price + (atr * atr_mult)
    target_down = start_price - (atr * 1)

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
# BACKTEST
# ==========================================================

def run_probability_engine(similar_data, full_data):

    results = {}
    atr_levels = [1, 2, 3, 4]

    for atr_mult in atr_levels:

        wins = 0
        losses = 0
        times = []

        for idx in similar_data.index:

            idx_full = full_data.index.get_loc(idx)

            sim = simulate_path(
                full_data,
                idx_full,
                atr_mult
            )

            if sim is None:
                continue

            if sim["result"] == "win":
                wins += 1
                times.append(sim["days"])
            else:
                losses += 1
                times.append(sim["days"])

        total = wins + losses

        if total == 0:
            results[atr_mult] = {
                "win_rate": 0,
                "ev": 0,
                "avg_time": 0,
                "samples": 0
            }
            continue

        win_rate = wins / total
        loss_rate = losses / total

        ev = (win_rate * atr_mult) - (loss_rate * 1)

        avg_time = np.mean(times) if times else 0

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

st.subheader("Probabilidade ATR (base histórica semelhante)")

results = run_probability_engine(similar_days, df)

# ==========================================================
# RESULTADOS
# ==========================================================

table_data = []

for k, v in results.items():

    table_data.append([
        f"+{k} ATR vs -1 ATR",
        f"{v['win_rate']*100:.2f}%",
        f"{v['ev']:.3f}",
        f"{v['avg_time']:.1f} dias",
        v["samples"]
    ])

table_df = pd.DataFrame(
    table_data,
    columns=[
        "Cenário",
        "Win Rate",
        "EV (ATR)",
        "Tempo Médio",
        "Amostras"
    ]
)

st.dataframe(table_df, use_container_width=True)

st.divider()

# ==========================================================
# MELHOR ESCOLHA
# ==========================================================

best = max(results.items(), key=lambda x: x[1]["ev"])

st.subheader("Melhor configuração estatística")

st.success(f"Melhor alvo: +{best[0]} ATR com EV = {best[1]['ev']:.3f}")

# ==========================================================
# HEATMAP
# ==========================================================

st.subheader("Heatmap de Confluência (Power Law x EV)")

bins = [-100, -50, -30, -20, -10, 0, 10, 20, 30, 50, 100]

df["PL_Bin"] = pd.cut(df["PL_Distance"], bins=bins)

heatmap_data = []

for b in df["PL_Bin"].dropna().unique():

    subset = df[df["PL_Bin"] == b]

    if len(subset) < 30:
        continue

    wins = 0
    losses = 0

    for idx in subset.sample(min(100, len(subset))).index:

        idx_full = df.index.get_loc(idx)

        sim = simulate_path(df, idx_full, 2)

        if sim is None:
            continue

        if sim["result"] == "win":
            wins += 1
        else:
            losses += 1

    total = wins + losses

    if total == 0:
        continue

    win_rate = wins / total

    ev = (win_rate * 2) - ((1 - win_rate) * 1)

    heatmap_data.append([str(b), win_rate, ev, total])

heatmap_df = pd.DataFrame(
    heatmap_data,
    columns=["Power Law Zone", "Win Rate", "EV", "Samples"]
)

st.dataframe(
    heatmap_df.sort_values("EV", ascending=False),
    use_container_width=True
)

# ==========================================================
# QUALIDADE
# ==========================================================

st.subheader("Qualidade Estatística da Amostra")

sample_count = len(similar_days)

if sample_count < 50:
    st.warning("Amostra baixa")
elif sample_count < 200:
    st.info("Amostra média")
else:
    st.success("Amostra robusta")

# ==========================================================
# EV DISTRIBUIÇÃO
# ==========================================================

st.subheader("Distribuição de EV")

ev_values = [v["ev"] for v in results.values()]

if len(ev_values) > 0:

    fig2 = go.Figure()
    fig2.add_trace(go.Histogram(x=ev_values, nbinsx=10))
    st.plotly_chart(fig2, use_container_width=True)

# ==========================================================
# RESUMO
# ==========================================================

st.subheader("Resumo Executivo")

current_regime = "NEUTRO"

if current_distance < -20:
    current_regime = "MUITO BARATO"
elif current_distance < 0:
    current_regime = "ABAIXO"
elif current_distance < 20:
    current_regime = "NEUTRO"
else:
    current_regime = "CARO"

best_ev = best[1]["ev"]

st.metric("Regime", current_regime)
st.metric("Melhor EV", f"{best_ev:.3f}")

# ==========================================================
# FINAL
# ==========================================================

st.subheader("Score Final")

ev_mean = np.mean(ev_values) if ev_values else 0

pl_score = max(0, 100 - abs(current_distance))

percentile_score = max(0, 100 - current_percentile)

final_score = (ev_mean * 25 * 0.5) + (pl_score * 0.3) + (percentile_score * 0.2)

final_score = min(max(final_score, 0), 100)

st.metric("Score Final", f"{final_score:.1f}")
