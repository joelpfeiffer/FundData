import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
pivot_full = pivot_full.sort_index().fillna(method="ffill")

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
    cutoff = pivot.index.max() - pd.Timedelta(days=days_map[tf])
    pivot = pivot.loc[pivot.index >= cutoff]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if len(pivot) < 2:
    st.warning("Te weinig data")
    st.dataframe(pivot)
    st.stop()

returns = pivot.pct_change().dropna()

if returns.empty:
    st.warning("Te weinig data voor returns")
    st.stop()

# CALCS
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

drawdown = pivot / pivot.cummax() - 1
max_dd = drawdown.min()

# TABS
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

# OVERVIEW
with tab1:
    st.subheader("Overview")

    best = ret.idxmax()
    worst = ret.idxmin()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
    c2.metric("Beste", best)
    c3.metric("Slechtste", worst)
    c4.metric("Vol", f"{vol.mean():.2f}")
    c5.metric("Sharpe", f"{sharpe.mean():.2f}")

    if vol.notna().any():
        risico_txt = f"{vol.idxmax()} ({vol.max():.2f})"
    else:
        risico_txt = "Geen data"

    st.info(f"""
Beste: {best} ({ret.max():.2f}%)
Slechtste: {worst} ({ret.min():.2f}%)
Risico: {risico_txt}
""")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    st.plotly_chart(fig,use_container_width=True)

# RAW DATA FIX
with tab7:
    raw = df[df["fund"].isin(selected)].copy()

    if raw.empty:
        st.warning("Geen data")
    else:
        st.dataframe(raw)
