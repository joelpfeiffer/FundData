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

if df.empty:
    st.error("No data loaded")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
selected = st.sidebar.multiselect("Funds", all_funds, default=all_funds[:5])

if not selected:
    st.warning("Select at least one fund")
    st.stop()

pivot = pivot_full[selected]

# =========================
# TIMEFRAME
# =========================
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

if len(pivot) < 2:
    st.error("Not enough data")
    st.stop()

returns = pivot.pct_change().dropna()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    section_title("Fund Prices", "Werkelijke prijs per fonds")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section_title("Momentum", "Recente stijging/daling")

    shift = 30 if len(pivot)>30 else 5
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        st.bar_chart(last)

# =========================
# RISK
# =========================
with tab3:
    section_title("Volatility", "Schommelingen")

    st.dataframe((returns.std()*np.sqrt(TRADING_DAYS)).to_frame("Vol"))

# =========================
# 🔥 HEATMAP (CRASH-PROOF)
# =========================
with tab4:

    section_title(
        "Return Heatmap",
        "Rendement (%) per periode. Groen = winst, rood = verlies."
    )

    df_full = pivot_full[selected]

    if len(df_full) < 2:
        st.warning("Not enough data for heatmap")
        st.stop()

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

    heatmap = heatmap.dropna(how="all")

    if heatmap.empty:
        st.warning("No heatmap data available")
        st.stop()

    # =========================
    # SPLIT
    # =========================
    short_cols = [c for c in ["1D","2D","3D","4D","1W","2W","3W"] if c in heatmap.columns]
    long_cols = [c for c in heatmap.columns if c not in short_cols]

    # =========================
    # SHORT TERM
    # =========================
    if short_cols:
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

    # =========================
    # LONG TERM
    # =========================
    if long_cols:
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

# =========================
# OPTIMIZER
# =========================
with tab5:
    section_title("Optimizer", "Beste verdeling")

    mean = returns.mean()
    cov = returns.cov()

    w = np.random.random(len(mean))
    w /= w.sum()

    st.dataframe(pd.DataFrame({"Fund":mean.index,"Weight":w}))

# =========================
# REBALANCE
# =========================
with tab6:
    section_title("Rebalance", "Simuleert portfolio groei")

    st.warning("Geen financieel advies")

    capital = st.number_input("Start (€)",100,1000000,10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)
    value = capital*(1+port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=value.index,y=value))
    st.plotly_chart(fig, use_container_width=True)