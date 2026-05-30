import streamlit as st
import asyncio
import websockets
import json
import pandas as pd
import numpy as np
import threading
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="BTC WebSocket Engine", layout="wide")
st.title("🏦 BTC Real-Time WebSocket Engine (Binance)")

# ==========================================================
# STATE STORE (SHARED MEMORY)
# ==========================================================
if "price_data" not in st.session_state:
    st.session_state.price_data = pd.DataFrame(columns=["time", "price"])

if "last_price" not in st.session_state:
    st.session_state.last_price = None

# ==========================================================
# WEBSOCKET THREAD
# ==========================================================
BINANCE_WS = "wss://stream.binance.com:9443/ws/btcusdt@trade"


def run_ws():

    async def listen():

        async with websockets.connect(BINANCE_WS) as ws:
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                price = float(data["p"])
                time = datetime.now()

                st.session_state.last_price = price

                new_row = pd.DataFrame([{
                    "time": time,
                    "price": price
                }])

                st.session_state.price_data = pd.concat(
                    [st.session_state.price_data, new_row],
                    ignore_index=True
                ).tail(500)

    asyncio.run(listen())


# start thread once
if "ws_started" not in st.session_state:
    thread = threading.Thread(target=run_ws, daemon=True)
    thread.start()
    st.session_state.ws_started = True

# ==========================================================
# INDICATORS (REAL TIME BUFFER)
# ==========================================================
df = st.session_state.price_data.copy()

if len(df) < 50:
    st.info("Aguardando fluxo de mercado...")
    st.stop()


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


df["EMA50"] = ema(df["price"], 50)

price = df["price"].iloc[-1]
ema50 = df["EMA50"].iloc[-1]

trend_ok = price > ema50

# ==========================================================
# SIGNAL ENGINE
# ==========================================================
if trend_ok:
    state = "LONG"
    signal = "🟢 FLOW BULLISH (ABOVE EMA50)"
else:
    state = "BEAR"
    signal = "🔴 FLOW BEARISH (BELOW EMA50)"

# ==========================================================
# UI
# ==========================================================
c1, c2 = st.columns(2)

c1.metric("BTC Live", f"${price:,.2f}")
c2.metric("EMA 50 (Flow)", f"${ema50:,.2f}")

st.divider()

if state == "LONG":
    st.success(signal)
else:
    st.error(signal)

# ==========================================================
# CHART REAL TIME
# ==========================================================
st.subheader("📊 Real-Time Price Flow")

st.line_chart(df.set_index("time")["price"])

# ==========================================================
# DEBUG INFO
# ==========================================================
st.write({
    "Last Update": datetime.now().strftime("%H:%M:%S"),
    "Buffer Size": len(df),
    "State": state
})
