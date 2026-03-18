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
# TIMEFRAME
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

if len(pivot) < 2:
    st.error("Not enough data in timeframe")
    st.stop()

# =========================
# RETURNS
# =========================
returns = pivot.pct_change().dropna()
returns_full = pivot_full[selected].pct_change().dropna()

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
# PERFORMANCE
# =========================
with tab2:
    if len(pivot) < 30:
        shift_days = max(1, int(len(pivot)/2))
    else:
        shift_days = 30

    mom = (pivot / pivot.shift(shift_days) - 1) * 100
    last = mom.iloc[-1].dropna()

    if not last.empty:
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
# 🔥 HEATMAP (FINAL FIXED COLORS)
# =========================
with tab4:
    st.subheader("Return heatmap")

    df_full = pivot_full[selected]
    latest_date = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,
        "6M":180,"1Y":365,"2Y":730,"5Y":1825
    }

    def calc_return(days):
        past_date = latest_date - pd.Timedelta(days=days)
        past_df = df_full[df_full.index <= past_date]

        if past_df.empty:
            return pd.Series(index=df_full.columns, dtype=float)

        return (df_full.loc[latest_date] / past_df.iloc[-1] - 1) * 100

    heatmap = pd.DataFrame({
        name: calc_return(days)
        for name, days in periods.items()
    }).round(2)

    short_cols = ["1D","2D","3D","4D","1W","2W","3W"]
    long_cols = [c for c in heatmap.columns if c not in short_cols]

    heat_short = heatmap[short_cols]
    heat_long = heatmap[long_cols]

    # SHORT TERM
    fig1 = go.Figure(data=go.Heatmap(
        z=heat_short.values,
        x=heat_short.columns,
        y=heat_short.index,
        colorscale=[
            [0, "#ff4d4d"],
            [0.5, "#ffffff"],
            [1, "#00cc66"]
        ],
        zmid=0,
        zmin=-3,
        zmax=3,
        text=heat_short.astype(str) + "%",
        texttemplate="%{text}"
    ))

    fig1.update_layout(
        title="Short term (<1M)",
        xaxis_title="Period",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig1, use_container_width=True)

    # LONG TERM
    fig2 = go.Figure(data=go.Heatmap(
        z=heat_long.values,
        x=heat_long.columns,
        y=heat_long.index,
        colorscale="RdYlGn",
        zmid=0,
        text=heat_long.astype(str) + "%",
        texttemplate="%{text}"
    ))

    fig2.update_layout(
        title="Long term (≥1M)",
        xaxis_title="Period",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig2, use_container_width=True)

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

    st.dataframe(pd.DataFrame({
        "Fund":mean.index,
        "Weight":best_w
    }).sort_values("Weight", ascending=False))

    port = (returns*best_w).sum(axis=1)
    cum = (1+port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum.index,y=cum))
    st.plotly_chart(style(fig,"Index"), use_container_width=True)

# =========================
# REBALANCE + MONTE CARLO
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