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

pivot = pivot_full[selected]
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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap", "Optimizer"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
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
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.to_frame("volatility"))

    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.to_frame("sharpe"))

# =========================
# HEATMAP
# =========================
with tab4:
    corr = returns.corr()
    st.dataframe(corr)

# =========================
# 🚀 OPTIMIZER
# =========================
with tab5:

    st.subheader("Portfolio Optimizer (Max Sharpe)")

    mean_returns = returns.mean()
    cov_matrix = returns.cov()

    num_assets = len(mean_returns)

    def portfolio_performance(weights):
        returns_port = np.sum(mean_returns * weights) * 252
        volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * 252, weights)))
        sharpe = returns_port / volatility
        return returns_port, volatility, sharpe

    # =========================
    # SIMULATIE
    # =========================
    num_portfolios = 5000

    results = []
    weights_record = []

    for _ in range(num_portfolios):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        ret, vol, sharpe = portfolio_performance(weights)

        results.append([ret, vol, sharpe])
        weights_record.append(weights)

    results = np.array(results)

    # =========================
    # BESTE PORTFOLIO
    # =========================
    best_idx = np.argmax(results[:,2])
    best_weights = weights_record[best_idx]

    best_df = pd.DataFrame({
        "Fund": mean_returns.index,
        "Weight": best_weights
    }).sort_values("Weight", ascending=False)

    st.subheader("Optimal Weights")
    st.dataframe(best_df)

    # =========================
    # PERFORMANCE CHART
    # =========================
    portfolio_returns = returns.copy()

    for i, fund in enumerate(mean_returns.index):
        portfolio_returns[fund] *= best_weights[i]

    portfolio = portfolio_returns.sum(axis=1)
    cumulative = (1 + portfolio).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative, name="Optimized Portfolio"))
    st.plotly_chart(style(fig), use_container_width=True)

    # =========================
    # DRAWDOWN
    # =========================
    drawdown = cumulative / cumulative.cummax() - 1

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown, name="Drawdown"))
    st.plotly_chart(style(fig), use_container_width=True)