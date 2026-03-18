import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
st.set_page_config(layout="wide", page_title="Funds Terminal")

# =========================
# TOOLTIP
# =========================
def title_with_tooltip(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# STYLE
# =========================
def style(fig, y_label):
    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title=y_label
    )
    fig.update_xaxes(showspikes=True)
    return fig

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load()

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Select funds")

selected = st.sidebar.multiselect(
    "Choose funds",
    all_funds,
    default=all_funds[:5]
)

if not selected:
    st.warning("Select at least one fund")
    st.stop()

pivot = pivot_full[selected]

# =========================
# TIMEFRAME
# =========================
st.sidebar.markdown("---")
st.sidebar.header("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset","Custom"])

if mode == "Preset":
    timeframe = st.sidebar.selectbox(
        "Range",
        ["1W","2W","1M","3M","6M","1Y","3Y","ALL"]
    )

    days_map = {
        "1W":7,"2W":14,"1M":30,
        "3M":90,"6M":180,
        "1Y":365,"3Y":1095
    }

    if timeframe != "ALL":
        end_date = pivot.index.max()
        start_date = end_date - pd.Timedelta(days=days_map[timeframe])
        pivot = pivot[pivot.index >= start_date]

else:
    start_date = st.sidebar.date_input("Start", pivot.index.min())
    end_date = st.sidebar.date_input("End", pivot.index.max())

    pivot = pivot[
        (pivot.index >= pd.to_datetime(start_date)) &
        (pivot.index <= pd.to_datetime(end_date))
    ]

if len(pivot) < 2:
    st.warning("Not enough data")
    st.stop()

returns = pivot.pct_change().dropna()

# =========================
# KPI
# =========================
perf = (pivot / pivot.iloc[0] - 1).iloc[-1] * 100

col1,col2,col3 = st.columns(3)
col1.metric("Best fund", perf.idxmax(), f"{perf.max():.2f}%")
col2.metric("Worst fund", perf.idxmin(), f"{perf.min():.2f}%")
col3.metric("Average return", "", f"{perf.mean():.2f}%")

# =========================
# TABS
# =========================
tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    title_with_tooltip("Fund prices","Werkelijke prijs in euro")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    st.plotly_chart(style(fig,"Price (€)"), use_container_width=True)

    title_with_tooltip("Normalized performance","Vergelijk groei")

    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index,y=norm[col],name=col))
    st.plotly_chart(style(fig,"Index (start = 1)"), use_container_width=True)

    title_with_tooltip("Drawdown","Daling vanaf piek")

    dd = norm / norm.cummax() - 1
    fig = go.Figure()
    for col in dd.columns:
        fig.add_trace(go.Scatter(x=dd.index,y=dd[col],name=col))
    st.plotly_chart(style(fig,"Drawdown (%)"), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip("Momentum (30d)","Laatste 30 dagen rendement")

    mom = (pivot / pivot.shift(30) - 1) * 100
    mom_last = mom.iloc[-1].dropna()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=mom_last.index,y=mom_last.values))
    fig.update_layout(
        xaxis_title="Fund",
        yaxis_title="Return (%)"
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    vol = returns.std()*np.sqrt(252)
    st.dataframe(vol.to_frame("Volatility"))

    sharpe = returns.mean()/returns.std()
    st.dataframe(sharpe.to_frame("Sharpe"))

# =========================
# HEATMAP
# =========================
with tab4:
    corr = returns.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr,
        x=corr.columns,
        y=corr.index,
        colorscale="RdYlGn"
    ))

    fig.update_layout(
        xaxis_title="Fund",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    weights = np.random.random(len(selected))
    weights /= weights.sum()

    st.dataframe(pd.DataFrame({
        "Fund":selected,
        "Weight":weights
    }))

# =========================
# REBALANCE + DISCLAIMER
# =========================
with tab6:

    st.warning(
        "⚠️ Dit is geen financieel advies. "
        "De berekeningen zijn gebaseerd op historische data en simulaties. "
        "Er kunnen geen rechten of garanties aan worden ontleend."
    )

    capital = st.number_input("Start (€)",100,1000000,10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    weights = np.array(list(weights.values()))
    weights /= weights.sum()

    port_returns = (returns*weights).sum(axis=1)
    cumulative = (1+port_returns).cumprod()
    value = capital * cumulative

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=value.index,y=value))
    st.plotly_chart(style(fig,"Portfolio value (€)"), use_container_width=True)