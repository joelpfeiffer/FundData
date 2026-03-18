import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide", page_title="Funds Terminal")

# =========================
# TOOLTIP HELPER
# =========================
def section_title(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
selected = st.sidebar.multiselect("Funds", all_funds, default=all_funds[:5])

if not selected:
    st.stop()

pivot = pivot_full[selected]

mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

returns = pivot.pct_change().dropna()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview","Performance","Risk","Heatmap"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    section_title("Fund Prices",
    "Werkelijke prijs per fonds over tijd")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section_title("Momentum",
    "Recente stijging of daling (%)")

    shift = 30 if len(pivot)>30 else 5
    mom = (pivot/pivot.shift(shift)-1)*100
    st.bar_chart(mom.iloc[-1].dropna())

# =========================
# RISK
# =========================
with tab3:
    section_title("Volatility",
    "Hoe sterk een fonds beweegt")

    st.dataframe((returns.std()*np.sqrt(TRADING_DAYS)).to_frame("Vol"))

# =========================
# 🔥 HEATMAP (HERSTELD)
# =========================
with tab4:

    section_title(
        "Return Heatmap",
        "Elke cel toont rendement (%) over een periode. Groen = winst, rood = verlies."
    )

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,
        "6M":180,"1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({
        k: calc(v) for k,v in periods.items()
    }).round(2)

    # SPLIT
    short_cols = ["1D","2D","3D","4D","1W","2W","3W"]
    long_cols = [c for c in heatmap.columns if c not in short_cols]

    # SHORT TERM
    fig1 = go.Figure(data=go.Heatmap(
        z=heatmap[short_cols].values,
        x=short_cols,
        y=heatmap.index,
        colorscale=[[0,"#ff4d4d"],[0.5,"#ffffff"],[1,"#00cc66"]],
        zmin=-3,zmax=3,zmid=0,
        text=heatmap[short_cols].astype(str)+"%",
        texttemplate="%{text}"
    ))

    st.plotly_chart(fig1, use_container_width=True)

    # LONG TERM
    fig2 = go.Figure(data=go.Heatmap(
        z=heatmap[long_cols].values,
        x=long_cols,
        y=heatmap.index,
        colorscale="RdYlGn",
        zmid=0,
        text=heatmap[long_cols].astype(str)+"%",
        texttemplate="%{text}"
    ))

    st.plotly_chart(fig2, use_container_width=True)