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
# TOOLTIP HELPER
# =========================
def title_with_tooltip(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# CHART STYLE (RULER)
# =========================
def apply_chart_style(fig):
    fig.update_layout(
        hovermode="x unified",
        spikedistance=1000,
        hoverlabel=dict(bgcolor="black")
    )

    fig.update_xaxes(
        showspikes=True,
        spikecolor="gray",
        spikesnap="cursor",
        spikemode="across",
        spikethickness=1
    )

    fig.update_yaxes(
        showspikes=True,
        spikecolor="gray",
        spikemode="across",
        spikethickness=1
    )

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

if df.empty:
    st.warning("No data available")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filters")

selected = st.sidebar.multiselect(
    "Funds",
    all_funds,
    default=all_funds[:5]
)

if not selected:
    st.warning("Select at least one fund")
    st.stop()

# =========================
# TIMEFRAME SELECTOR
# =========================
st.sidebar.header("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset", "Custom"])

if mode == "Preset":
    timeframe = st.sidebar.selectbox(
        "Range",
        ["1W", "2W", "1M", "3M", "6M", "1Y", "3Y", "ALL"]
    )

    days_map = {
        "1W":7, "2W":14, "1M":30,
        "3M":90, "6M":180,
        "1Y":365, "3Y":1095
    }

    pivot = pivot_full[selected]

    if timeframe != "ALL":
        end_date = pivot.index.max()
        start_date = end_date - pd.Timedelta(days=days_map[timeframe])
        pivot = pivot[pivot.index >= start_date]

else:
    min_date = pivot_full.index.min()
    max_date = pivot_full.index.max()

    start_date = st.sidebar.date_input("Start", min_date)
    end_date = st.sidebar.date_input("End", max_date)

    pivot = pivot_full[selected]
    pivot = pivot[
        (pivot.index >= pd.to_datetime(start_date)) &
        (pivot.index <= pd.to_datetime(end_date))
    ]

# =========================
# SAFETY
# =========================
if len(pivot) < 2:
    st.warning("Not enough data for selected timeframe")
    st.stop()

returns = pivot.pct_change().dropna()

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
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap"
])

# =========================
# OVERVIEW (WITH RULER)
# =========================
with tab1:

    title_with_tooltip("Fund prices", "Absolute prijs van fondsen")
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(apply_chart_style(fig), use_container_width=True)

    title_with_tooltip("Normalized performance", "Relatieve groei")
    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(apply_chart_style(fig), use_container_width=True)

    title_with_tooltip("Drawdown", "Daling vanaf piek")
    dd = norm / norm.cummax() - 1
    fig = go.Figure()
    for col in dd.columns:
        fig.add_trace(go.Scatter(x=dd.index, y=dd[col], name=col))
    st.plotly_chart(apply_chart_style(fig), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip("Momentum (30d)", "Laatste 30 dagen rendement")

    mom = (pivot / pivot.shift(30) - 1) * 100
    mom_last = mom.iloc[-1].dropna()

    if len(mom_last) == 0:
        st.info("Not enough data")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mom_last.index, y=mom_last.values))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    title_with_tooltip("Volatility", "Risico")
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.sort_values(ascending=False).to_frame("volatility"))

    title_with_tooltip("Sharpe ratio", "Rendement per risico")
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

# =========================
# HEATMAP (CONTRAST FIX)
# =========================
with tab4:
    title_with_tooltip("Return heatmap", "Groen = positief")

    latest_date = df["date"].max()

    def calc_return(days):
        res = {}
        for fund in df["fund"].unique():
            f = df[df["fund"] == fund]
            current = f.iloc[-1]["price"]
            past = f[f["date"] <= latest_date - pd.Timedelta(days=days)]

            if past.empty:
                res[fund] = np.nan
            else:
                res[fund] = (current / past.iloc[-1]["price"] - 1) * 100
        return pd.Series(res)

    periods = {
        "1D":1,"3D":3,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,
        "1Y":365,"3Y":1095,"5Y":1825
    }

    heatmap = pd.DataFrame({k: calc_return(v) for k,v in periods.items()})
    heatmap = heatmap.loc[selected]

    z = heatmap.values
    x = heatmap.columns
    y = heatmap.index

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=x,
        y=y,
        colorscale=[
            [0, "#ff4d4d"],
            [0.5, "#ffd966"],
            [1, "#70ad47"]
        ],
        colorbar=dict(title="Return %")
    ))

    for i in range(len(y)):
        for j in range(len(x)):
            val = z[i][j]
            if pd.notna(val):
                color = "white" if val < 0 or val > 5 else "black"
                fig.add_annotation(
                    x=x[j],
                    y=y[i],
                    text=f"{val:.2f}%",
                    showarrow=False,
                    font=dict(color=color)
                )

    st.plotly_chart(fig, use_container_width=True)