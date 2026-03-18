import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide", page_title="Funds Dashboard")

# =========================
# DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
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

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# OVERVIEW (ongewijzigd)
# =========================
with tab1:
    st.subheader("Prijsontwikkeling")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE (ongewijzigd)
# =========================
with tab2:
    st.subheader("Momentum")

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        st.bar_chart(last.sort_values(ascending=False))

# =========================
# RISK (ongewijzigd)
# =========================
with tab3:
    st.subheader("Volatility")
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol)

    st.subheader("Sharpe")
    sharpe = (returns.mean()*TRADING_DAYS)/vol
    st.dataframe(sharpe)

# =========================
# HEATMAP (ongewijzigd)
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"2D":2,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,
        "1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()})

    st.dataframe(heatmap.round(2))

# =========================
# OPTIMIZER (ongewijzigd)
# =========================
with tab5:
    st.subheader("Optimizer")
    w = np.random.random(len(selected))
    w /= w.sum()
    st.dataframe(pd.DataFrame({"Fund": selected, "Weight": w}))

# =========================
# ✅ REBALANCE (GEFIXT)
# =========================
with tab6:

    st.subheader("Portfolio verdeling (%)")

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    # =========================
    # FIX: alloc sync
    # =========================
    if "alloc" not in st.session_state:
        st.session_state.alloc = {}

    # verwijder oude
    st.session_state.alloc = {
        k: v for k, v in st.session_state.alloc.items() if k in selected
    }

    # voeg toe
    for fund in selected:
        if fund not in st.session_state.alloc:
            st.session_state.alloc[fund] = int(100/len(selected))

    # =========================
    # GRID
    # =========================
    cols = st.columns(len(selected))

    for i, fund in enumerate(selected):
        with cols[i]:
            st.markdown(f"**{fund}**")
            st.session_state.alloc[fund] = st.number_input(
                "%",
                0, 100,
                st.session_state.alloc[fund],
                key=f"alloc_{fund}"
            )

    total = sum(st.session_state.alloc.values())

    if total != 100:
        st.error(f"Totaal = {total}% (moet 100%)")
        st.stop()
    else:
        st.success("Totaal = 100%")

    # =========================
    # FIX: weights align
    # =========================
    weights = pd.Series(st.session_state.alloc) / 100
    weights = weights[weights.index.isin(returns.columns)]

    try:
        port = (returns[weights.index] * weights).sum(axis=1)
    except:
        st.error("Portfolio berekening fout")
        st.stop()

    # =========================
    # SIM
    # =========================
    st.subheader("Historische simulatie")

    value = capital * (1 + port).cumprod()
    st.line_chart(value)

    # =========================
    # MONTE CARLO (FIX)
    # =========================
    st.subheader("Monte Carlo")

    if len(port) > 20:
        mu = port.mean()
        sigma = port.std()

        if sigma > 0:
            sims = np.random.normal(mu, sigma, (252, 300))
            sims = capital * np.cumprod(1 + sims, axis=0)

            mc = pd.DataFrame({
                "Worst": np.percentile(sims,10,axis=1),
                "Expected": np.percentile(sims,50,axis=1),
                "Best": np.percentile(sims,90,axis=1)
            })

            st.line_chart(mc)
        else:
            st.warning("Geen variatie in data")
    else:
        st.info("Te weinig data")

    # =========================
    # DISCLAIMER
    # =========================
    st.warning(
        "Dit is geen financieel advies. Resultaten uit het verleden bieden geen garantie voor de toekomst."
    )