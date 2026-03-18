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

st.set_page_config(layout="wide", page_title="Funds Dashboard")

# =========================
# TOOLTIP
# =========================
def section(title, tooltip):
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
    st.error("Geen data geladen")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect(
    "Selecteer fondsen",
    funds,
    default=funds[:5]
)

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
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
    st.error("Niet genoeg data")
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
    section("Prijsontwikkeling", "Prijs per fonds over tijd")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section("Momentum", "Rendement over recente periode")

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if last.empty:
        st.warning("Geen data")
    else:
        fig = go.Figure(go.Bar(
            x=last.index,
            y=last.values
        ))
        st.plotly_chart(fig, use_container_width=True)

    # Ranking
    section("Ranking", "Beste en slechtste fondsen")

    perf = last.sort_values(ascending=False)

    col1, col2 = st.columns(2)

    with col1:
        st.write("Top performers")
        st.dataframe(perf.head(5))

    with col2:
        st.write("Slechtste performers")
        st.dataframe(perf.tail(5))

# =========================
# RISK
# =========================
with tab3:
    section("Volatility", "Schommelingen van fondsen")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

# =========================
# HEATMAP
# =========================
with tab4:
    section("Heatmap", "Rendement per periode (%)")

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,"1Y":365,"2Y":730
    }

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({
        k: calc(v) for k,v in periods.items()
    }).dropna(how="all")

    if heatmap.empty:
        st.warning("Geen heatmap data")
    else:
        fig = go.Figure(data=go.Heatmap(
            z=heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            colorscale="RdYlGn",
            zmid=0,
            text=heatmap.round(2).astype(str)+"%",
            texttemplate="%{text}"
        ))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    section("Portfolio Optimizer", "Simpele gewichtsverdeling")

    weights = np.random.random(len(selected))
    weights /= weights.sum()

    st.dataframe(pd.DataFrame({
        "Fund": selected,
        "Weight": weights
    }))

# =========================
# REBALANCE
# =========================
with tab6:
    section("Rebalance Simulator", "Simuleert portfolio groei")

    st.warning("Dit is geen financieel advies")

    capital = st.number_input("Start bedrag", 100, 1000000, 10000)

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