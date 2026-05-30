import streamlit as st
import pandas as pd
import numpy as np
import asyncio
import websockets
import json
import threading
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC WebSocket Engine PRO", layout="wide")
st.title("🏦 BTC Real-Time Engine (Stable Version)")

# ==========================================================
# MEMORY
# ==========================================================
if "price_data" not in st.session_state:
    st.session_state.price_data = pd.DataFrame(columns=["time", "price"])

if "buffer_ready" not in st.session_state:
    st.session_state.buffer_ready = False

# ==========================================================
# WEBSOCKET
# ==========================================================
WS = "wss://stream.binance.com:9443/ws/btcusdt@trade"


def ws_loop():

    async def run():
        async with websockets.connect(WS) as websocket:

            while True:
                msg = await websocket.recv()
                data = json.loads(msg)

                price = float(data["p"])
                now = datetime.utcnow()

                new_row = pd.DataFrame([{
                    "time": now,
                    "price": price
                }])

                st.session_state.price_data = pd.concat(
                    [st.session_state.price_data,
                     new_row],
                    ignore_index=True
                ).tail(300)

                st.session_state.buffer_ready = True

    asyncio.run(run())


# start once
if "ws_started" not in st.session_state:
    thread = threading.Thread(target=ws_loop, daemon=True)
    thread.start()
    st.session_state.ws_started = True

# ==========================================================
# ENGINE LOOP SAFE (NUNCA BLOQUEIA APP)
# ==========================================================
df = st.session_state.price_data.copy()

# SEM STOP, SEM TRAVAR APP
if len(df) < 5:
    st.warning("Conectando ao fluxo de mercado... (aguarde alguns segundos)")
    st.stop()

# ==========================================================
# INDICADORES
# ==========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


df["EMA20"] = ema(df["price"], 20)

price = df["price"].iloc[-1]
ema20 = df["EMA20"].iloc[-1]

trend = price > ema20

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if trend:
    state = "LONG"
    signal = "🟢 FLUXO POSITIVO (ACIMA DA EMA20)"
else:
    state = "SHORT"
    signal = "🔴 FLUXO NEGATIVO (ABAIXO DA EMA20)"

# ==========================================================
# UI
# ==========================================================
c1, c2 = st.columns(2)

c1.metric("BTC Live", f"${price:,.2f}")
c2.metric("EMA 20", f"${ema20:,.2f}")

st.divider()

if state == "LONG":
    st.success(signal)
else:
    st.error(signal)

# ==========================================================
# CHART REAL TIME
# ==========================================================
st.subheader("📊 Fluxo de Preço em Tempo Real")

st.line_chart(df.set_index("time")["price"])

# ==========================================================
# DEBUG
# ==========================================================
st.write({
    "Buffer size": len(df),
    "Status": state,
    "Last update": datetime.utcnow().strftime("%H:%M:%S UTC")
})
