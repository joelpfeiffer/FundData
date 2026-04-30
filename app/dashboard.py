# === FIXED VERSION (key fixes marked with ### FIX) ===

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# SIDEBAR
st.sidebar.title("Instellingen")
funds = list(pivot_full.columns)
selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])
mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

if mode == "Preset":
    tf = st.sidebar.selectbox("Periode", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}
else:
    start = st.sidebar.date_input("Start", pivot_full.index.min())
    end = st.sidebar.date_input("End", pivot_full.index.max())

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if pivot.empty:
    st.warning("Geen data in deze periode")
    st.stop()

returns = pivot.pct_change().dropna()

# === FIX 1: voorkomen lege returns ===
if returns.empty:
    st.warning("Te weinig data om metrics te berekenen (minimaal 2 datapunten nodig)")
    st.stop()

# CALCULATIONS
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100 if len(pivot) > 1 else None
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

drawdown = pivot / pivot.cummax() - 1
max_dd = drawdown.min()

# TABS
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

with tab1:
    st.subheader("Overview")

    start_date = pivot.index.min().strftime("%d-%m-%Y")
    end_date = pivot.index.max().strftime("%d-%m-%Y")
    days = (pivot.index.max() - pivot.index.min()).days

    st.caption(f"Data van {start_date} tot {end_date} ({days} dagen)")

    if ret is not None:
        best = ret.idxmax()
        worst = ret.idxmin()

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
        c2.metric("Beste fonds", best)
        c3.metric("Slechtste fonds", worst)
        c4.metric("Volatiliteit", f"{vol.mean():.2f}")
        c5.metric("Sharpe", f"{sharpe.mean():.2f}")

    # === FIX 2: veilige volatiliteit ===
    if vol.notna().any():
        hoogste_risico = vol.idxmax()
        hoogste_vol = vol.max()
        risico_txt = f"⚠️ Hoogste risico: {hoogste_risico} (volatiliteit {hoogste_vol:.2f})"
    else:
        risico_txt = "⚠️ Geen volatiliteitsdata beschikbaar"

    if ret is not None:
        st.info(f"""
📈 Beste performer: {best} (+{ret.max():.2f}%)

📉 Slechtste performer: {worst} ({ret.min():.2f}%)

{risico_txt}

💡 Interpretatie:
- Hoge volatiliteit = grotere schommelingen
- Hoog rendement + lage volatiliteit = sterke combinatie
""")

    st.markdown("---")

    fig = go.Figure()
    benchmark = pivot.mean(axis=1)

    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.add_trace(go.Scatter(x=pivot.index, y=benchmark, name="Benchmark", line=dict(dash="dash")))

    st.plotly_chart(fig, use_container_width=True)

# (rest van script blijft ongewijzigd)
