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
# LOAD
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

if df.empty:
    st.error("Geen data")
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

pivot = pivot_full[selected]

# =========================
# RETURNS
# =========================
returns = pivot.pct_change().dropna()

if returns.empty:
    st.error("Niet genoeg data")
    st.stop()

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
    st.subheader("Prijsontwikkeling")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            name=col
        ))

    # 👉 RULER / CROSSHAIR
    fig.update_layout(
        hovermode="x unified",
        xaxis=dict(showspikes=True),
        yaxis=dict(showspikes=True)
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # TRENDS (GENORMALISEERD)
    # =========================
    st.subheader("Trends (genormaliseerd)")

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
        xaxis=dict(showspikes=True),
        yaxis=dict(showspikes=True)
    )

    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum")

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        fig = go.Figure(go.Bar(
            x=last.index,
            y=last.values
        ))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK (UPGRADE)
# =========================
with tab3:
    st.subheader("Volatility")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    # =========================
    # CORRELATION MATRIX (RAVELS)
    # =========================
    st.subheader("Correlation Matrix")

    corr = returns.corr()

    fig = px.imshow(
        corr,
        text_auto=True,
        color_continuous_scale="RdBu",
        zmin=-1,
        zmax=1
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # DRAWDOWN
    # =========================
    st.subheader("Drawdown")

    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak * 100

    fig = go.Figure()
    for col in drawdown.columns:
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown[col],
            name=col
        ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    st.subheader("Heatmap")

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,"1Y":365
    }

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({
        k: calc(v) for k,v in periods.items()
    }).dropna(how="all")

    if not heatmap.empty:
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
    st.subheader("Optimizer")

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({
        "Fund": selected,
        "Weight": w
    }))

# =========================
# REBALANCE + MONTE CARLO
# =========================
with tab6:
    st.subheader("Rebalance Simulator")

    st.warning("Dit is geen financieel advies")

    capital = st.number_input("Start (€)", 100, 1000000, 10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)
    value = capital*(1+port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=value.index,y=value,name="Portfolio"))
    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # MONTE CARLO
    # =========================
    st.subheader("Monte Carlo")

    if len(returns) > 10:
        sims = 100
        horizon = 252

        mean = port.mean()
        std = port.std()

        fig = go.Figure()

        for _ in range(20):
            r = np.random.normal(mean, std, horizon)
            sim = capital * np.cumprod(1+r)
            fig.add_trace(go.Scatter(y=sim, opacity=0.2))

        st.plotly_chart(fig, use_container_width=True)