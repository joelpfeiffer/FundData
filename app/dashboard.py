import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide", page_title="Funds Dashboard")

def section(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()
pivot_full = df.pivot(index="date", columns="fund", values="price")

funds = list(pivot_full.columns)
selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

if not selected:
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset", "Custom"])

pivot = pivot_full[selected]

if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","3Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365,"3Y":1095}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
else:
    start = st.sidebar.date_input("Start date", pivot.index.min())
    end = st.sidebar.date_input("End date", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

returns = pivot.pct_change().dropna()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# REBALANCE (FIXED)
# =========================
with tab6:
    section("Rebalance Simulator", "Simuleert portfolio op basis van gewichten")

    st.warning(
        "Deze simulatie is uitsluitend bedoeld voor informatieve en educatieve doeleinden. "
        "Er kunnen geen rechten aan worden ontleend. Resultaten uit het verleden bieden geen garantie voor de toekomst."
    )

    capital = st.number_input("Start (€)", 100, 1000000, 10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)

    # =========================
    # 📈 HISTORISCHE TREND (HERSTELD)
    # =========================
    section("Historische portfolio waarde", "Werkelijke ontwikkeling op basis van data")

    value = capital*(1+port).cumprod()

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=value.index,y=value,name="Portfolio"))

    fig_hist.update_layout(
        xaxis_title="Date",
        yaxis_title="Portfolio (€)"
    )

    st.plotly_chart(fig_hist, use_container_width=True)

    # =========================
    # 🎲 MONTE CARLO (3 LIJNEN)
    # =========================
    section("Monte Carlo Simulation", "Toekomstscenario’s")

    if len(port) < 5:
        st.warning("Te weinig data")
    else:
        mean = port.mean()
        std = port.std()

        horizon = 252
        sims = 1000

        simulations = np.random.normal(mean, std, (horizon, sims))
        simulations = capital * np.cumprod(1 + simulations, axis=0)

        worst = np.percentile(simulations, 10, axis=1)
        expected = np.percentile(simulations, 50, axis=1)
        best = np.percentile(simulations, 90, axis=1)

        fig_mc = go.Figure()

        fig_mc.add_trace(go.Scatter(y=worst, name="Worst case (P10)", line=dict(color="red")))
        fig_mc.add_trace(go.Scatter(y=expected, name="Expected (P50)", line=dict(color="blue")))
        fig_mc.add_trace(go.Scatter(y=best, name="Best case (P90)", line=dict(color="green")))

        fig_mc.update_layout(
            xaxis_title="Days",
            yaxis_title="Portfolio (€)"
        )

        st.plotly_chart(fig_mc, use_container_width=True)