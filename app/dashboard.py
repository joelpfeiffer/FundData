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
def style(fig):
    fig.update_layout(hovermode="x unified")
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

if df.empty:
    st.warning("No data available")
    st.stop()

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

# =========================
# TIMEFRAME SELECTOR
# =========================
st.sidebar.markdown("---")
st.sidebar.header("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset", "Custom"])

pivot = pivot_full[selected]

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

    if timeframe != "ALL":
        end_date = pivot.index.max()
        start_date = end_date - pd.Timedelta(days=days_map[timeframe])
        pivot = pivot[pivot.index >= start_date]

else:
    min_date = pivot.index.min()
    max_date = pivot.index.max()

    start_date = st.sidebar.date_input("Start date", min_date)
    end_date = st.sidebar.date_input("End date", max_date)

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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap", "Optimizer", "Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    title_with_tooltip("Fund prices",
        "Dit toont de echte prijs van elk fonds over tijd.")
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

    title_with_tooltip("Normalized performance",
        "Alle fondsen starten gelijk (op 1), zodat je prestaties kunt vergelijken.")
    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

    title_with_tooltip("Drawdown",
        "Laat zien hoe ver een fonds daalt vanaf zijn hoogste punt.")
    dd = norm / norm.cummax() - 1
    fig = go.Figure()
    for col in dd.columns:
        fig.add_trace(go.Scatter(x=dd.index, y=dd[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip("Momentum (30 dagen)",
        "Laatste 30 dagen rendement.")
    mom = (pivot / pivot.shift(30) - 1) * 100
    mom_last = mom.iloc[-1].dropna()

    if len(mom_last) > 0:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mom_last.index, y=mom_last.values))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    title_with_tooltip("Volatility",
        "Hoe sterk de prijs schommelt (risico).")
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.to_frame("volatility"))

    title_with_tooltip("Sharpe ratio",
        "Rendement per risico. Hoger = beter.")
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.to_frame("sharpe"))

# =========================
# HEATMAP
# =========================
with tab4:
    title_with_tooltip("Correlation heatmap",
        "Laat zien hoe fondsen samen bewegen.")
    st.dataframe(returns.corr())

# =========================
# OPTIMIZER
# =========================
with tab5:
    title_with_tooltip("Portfolio optimizer",
        "Zoekt een slimme verdeling van je geld over fondsen.")

    weights = np.random.random(len(selected))
    weights /= weights.sum()

    df_weights = pd.DataFrame({
        "Fund": selected,
        "Weight": weights
    }).sort_values("Weight", ascending=False)

    st.dataframe(df_weights)

# =========================
# REBALANCE
# =========================
with tab6:
    title_with_tooltip("Rebalance simulator",
        "Simuleert hoe je portfolio groeit met periodiek herbalanceren.")

    weights = {}
    cols = st.columns(len(selected))

    for i, fund in enumerate(selected):
        weights[fund] = cols[i].number_input(fund, 0.0, 1.0, 1/len(selected))

    weights = np.array(list(weights.values()))
    weights /= weights.sum()

    portfolio = (returns * weights).sum(axis=1)
    cumulative = (1 + portfolio).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative))
    st.plotly_chart(style(fig), use_container_width=True)