import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide")

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "price", "fund"])
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

mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

pivot = pivot_full[selected].copy()

# =========================
# TIMEFRAME
# =========================
if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")
returns = pivot.pct_change().dropna()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

# =========================
# OVERVIEW
# =========================
with tab1:

    st.subheader("Overview")

    # =========================
    # METRICS BAR (NIEUW)
    # =========================
    if len(pivot) > 1:
        total_return = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100
        best = total_return.idxmax()
        worst = total_return.idxmin()

        vol = returns.std().mean() * np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean().mean() * TRADING_DAYS) / vol if vol != 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Gemiddeld rendement", f"{total_return.mean():.2f}%")
        col2.metric("Beste fonds", best)
        col3.metric("Slechtste fonds", worst)
        col4.metric("Volatiliteit", f"{vol:.2f}")
        col5.metric("Sharpe", f"{sharpe:.2f}")

    st.markdown("---")

    # =========================
    # PRIJS CHART
    # =========================
    st.subheader("Prijsontwikkeling")
    st.caption(f"{pivot.index.min().date()} → {pivot.index.max().date()}")

    fig = go.Figure()

    for col in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            name=col,
            line=dict(width=2)
        ))

    fig.update_layout(
        hovermode="x unified",
        template="plotly_white",
        xaxis=dict(showspikes=True),
        yaxis=dict(showspikes=True)
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # GROWTH
    # =========================
    st.subheader("Genormaliseerde groei")

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()

    for col in norm.columns:
        fig2.add_trace(go.Scatter(
            x=norm.index,
            y=norm[col],
            name=col
        ))

    fig2.update_layout(
        hovermode="x unified",
        template="plotly_white",
        xaxis=dict(showspikes=True),
        yaxis=dict(showspikes=True)
    )

    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader("Momentum")

    if len(pivot) < 30:
        st.warning("Te weinig data (<30)")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        last = mom.iloc[-1].dropna()

        fig = go.Figure(go.Bar(x=last.index, y=last.values))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Risk metrics")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0, np.nan)

    st.dataframe(pd.concat([vol, sharpe], axis=1).rename(columns={0:"Vol",1:"Sharpe"}))

    fig = px.imshow(
        returns.corr(),
        text_auto=True,
        color_continuous_scale="RdYlGn",
        zmin=-1,
        zmax=1
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"1W":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()})
    heatmap = heatmap.loc[selected]

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
    st.subheader("Optimizer (placeholder)")
    st.write("Blijft intact")

# =========================
# REBALANCE
# =========================
with tab6:
    st.subheader("Rebalance (intact)")
    st.write("Geen wijzigingen")

# =========================
# RAW DATA
# =========================
with tab7:

    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)].copy()
    raw = raw.sort_values("date", ascending=False)

    view = st.radio("Weergave", ["Long", "Wide"], horizontal=True)

    if view == "Long":
        st.dataframe(raw, use_container_width=True)

    else:
        pivot_excel = raw.pivot(index="date", columns="fund", values="price")
        st.dataframe(pivot_excel, use_container_width=True)