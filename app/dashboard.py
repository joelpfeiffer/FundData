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
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "price", "fund"])
    return df.sort_values("date")

df = load()

if df.empty:
    st.error("No data loaded")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
pivot_full = pivot_full.dropna(how="all")

all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR - FUNDS
# =========================
st.sidebar.header("Funds")

selected = st.sidebar.multiselect(
    "Select funds",
    all_funds,
    default=all_funds[:5]
)

if not selected:
    st.warning("Select at least one fund")
    st.stop()

pivot = pivot_full[selected]

# =========================
# SIDEBAR - TIMEFRAME
# =========================
st.sidebar.markdown("---")
st.sidebar.header("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset", "Custom"])

if mode == "Preset":
    tf = st.sidebar.selectbox(
        "Range",
        ["1W","2W","1M","3M","6M","1Y","3Y","ALL"]
    )

    days_map = {
        "1W":7,"2W":14,"1M":30,
        "3M":90,"6M":180,
        "1Y":365,"3Y":1095
    }

    if tf != "ALL":
        end = pivot.index.max()
        start = end - pd.Timedelta(days=days_map[tf])
        pivot = pivot[pivot.index >= start]

else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())

    pivot = pivot[
        (pivot.index >= pd.to_datetime(start)) &
        (pivot.index <= pd.to_datetime(end))
    ]

# =========================
# VALIDATIE
# =========================
if len(pivot) < 2:
    st.error("Not enough data in selected timeframe")
    st.stop()

# =========================
# RETURNS
# =========================
returns = pivot.pct_change().dropna()
returns_full = pivot_full[selected].pct_change().dropna()

if returns.empty:
    st.error("No return data")
    st.stop()

# =========================
# KPI
# =========================
perf = (pivot / pivot.iloc[0] - 1).iloc[-1] * 100

col1, col2, col3 = st.columns(3)
col1.metric("Best fund", perf.idxmax(), f"{perf.max():.2f}%")
col2.metric("Worst fund", perf.idxmin(), f"{perf.min():.2f}%")
col3.metric("Average return", "", f"{perf.mean():.2f}%")

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
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(style(fig,"Price (€)"), use_container_width=True)

    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(style(fig,"Index (start=1)"), use_container_width=True)

# =========================
# PERFORMANCE (FIXED)
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) < 30:
        shift_days = max(1, int(len(pivot) / 2))
        st.info(f"Using {shift_days}-day momentum (limited data)")
    else:
        shift_days = 30

    mom = (pivot / pivot.shift(shift_days) - 1) * 100
    last = mom.iloc[-1].dropna()

    if last.empty:
        st.warning("No momentum data available")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=last.index, y=last.values))
        fig.update_layout(xaxis_title="Fund", yaxis_title="Return (%)")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = returns.mean() / returns.std()

    st.dataframe(vol.to_frame("Volatility"))
    st.dataframe(sharpe.to_frame("Sharpe"))

# =========================
# HEATMAP (FIXED)
# =========================
with tab4:
    st.subheader("Correlation heatmap (full dataset)")

    if returns_full.empty:
        st.warning("Not enough data for heatmap")
    else:
        corr = returns_full.corr()

        fig = go.Figure(data=go.Heatmap(
            z=corr,
            x=corr.columns,
            y=corr.index,
            colorscale="RdYlGn",
            zmin=-1,
            zmax=1
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
    mean = returns.mean()
    cov = returns.cov()

    best_s = -np.inf
    best_w = None

    for _ in range(2000):
        w = np.random.random(len(mean))
        w /= w.sum()

        r = np.sum(mean*w)*TRADING_DAYS
        v = np.sqrt(np.dot(w.T, np.dot(cov*TRADING_DAYS, w)))

        if v == 0:
            continue

        s = r/v

        if s > best_s:
            best_s = s
            best_w = w

    if best_w is None:
        st.error("Optimization failed")
        st.stop()

    st.dataframe(pd.DataFrame({
        "Fund":mean.index,
        "Weight":best_w
    }).sort_values("Weight", ascending=False))

    port = (returns * best_w).sum(axis=1)
    cum = (1+port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum.index,y=cum))
    st.plotly_chart(style(fig,"Index"), use_container_width=True)

# =========================
# REBALANCE
# =========================
with tab6:
    st.warning("Dit is geen financieel advies")

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
    st.plotly_chart(style(fig,"Portfolio (€)"), use_container_width=True)