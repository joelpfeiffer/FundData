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

# -------------------------
# OVERVIEW (UNCHANGED)
# -------------------------
with tab1:
    section("Prijsontwikkeling (€)", "Toont de absolute prijs van elk fonds")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(xaxis_title="Date", yaxis_title="Price (€)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# -------------------------
# PERFORMANCE (UNCHANGED)
# -------------------------
with tab2:
    section("Momentum (%)", "Rendement over recente periode")

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        fig = go.Figure(go.Bar(x=last.index, y=last.values))
        fig.update_layout(xaxis_title="Fund", yaxis_title="Return (%)")
        st.plotly_chart(fig, use_container_width=True)

# -------------------------
# RISK (UNCHANGED)
# -------------------------
with tab3:
    section("Volatility", "Risico")
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    section("Sharpe Ratio", "Rendement per risico")
    sharpe = (returns.mean()*TRADING_DAYS) / vol
    st.dataframe(sharpe.to_frame("Sharpe"))

    section("Correlation Matrix", "Samenhang")
    fig = px.imshow(returns.corr(), text_auto=True, color_continuous_scale="RdBu", zmin=-1, zmax=1)
    st.plotly_chart(fig, use_container_width=True)

# -------------------------
# HEATMAP (UNCHANGED)
# -------------------------
with tab4:
    section("Heatmap", "Rendement per periode")

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {"1D":1,"2D":2,"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365,"2Y":730,"5Y":1825}

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()}).dropna(how="all")

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

# -------------------------
# OPTIMIZER (UNCHANGED)
# -------------------------
with tab5:
    section("Optimizer", "Gewichten")
    w = np.random.random(len(selected))
    w /= w.sum()
    st.dataframe(pd.DataFrame({"Fund": selected, "Weight": w}))

# -------------------------
# REBALANCE + FIXED MONTE CARLO
# -------------------------
with tab6:
    section("Rebalance Simulator", "Portfolio groei")

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
    fig.add_trace(go.Scatter(x=value.index,y=value))
    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # 🔥 MONTE CARLO FIXED
    # =========================
    section("Monte Carlo Simulation", "Toekomstscenario’s")

    if len(port) < 5:
        st.warning("Te weinig data voor simulatie")
    else:
        mean = port.mean()
        std = port.std()

        horizon = 252
        sims = 500

        simulations = np.random.normal(mean, std, (horizon, sims))
        simulations = capital * np.cumprod(1 + simulations, axis=0)

        p10 = np.percentile(simulations, 10, axis=1)
        p50 = np.percentile(simulations, 50, axis=1)
        p90 = np.percentile(simulations, 90, axis=1)

        fig = go.Figure()

        fig.add_trace(go.Scatter(y=p90, line=dict(width=0)))
        fig.add_trace(go.Scatter(y=p10, fill='tonexty', name="Range (10-90%)"))
        fig.add_trace(go.Scatter(y=p50, name="Expected"))

        fig.update_layout(
            xaxis_title="Days",
            yaxis_title="Portfolio (€)"
        )

        st.plotly_chart(fig, use_container_width=True)