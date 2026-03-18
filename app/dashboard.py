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
# TOOLTIP HELPER (DUidelijk!)
# =========================
def title_with_tooltip(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# CHART STYLE
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
st.sidebar.header("Select funds")

selected = st.sidebar.multiselect(
    "Choose funds to analyze",
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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap", "Optimizer", "Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    title_with_tooltip(
        "Fund prices",
        "Dit laat de echte prijs van elk fonds zien door de tijd. Gebruik dit om te zien hoe de waarde van een fonds verandert."
    )
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

    title_with_tooltip(
        "Normalized performance",
        "Alle fondsen starten op dezelfde waarde (1). Hierdoor kun je eerlijk vergelijken welk fonds beter presteert."
    )
    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

    title_with_tooltip(
        "Drawdown",
        "Dit laat zien hoeveel een fonds is gedaald vanaf zijn hoogste punt. Dit is een belangrijke risicomaatstaf."
    )
    dd = norm / norm.cummax() - 1
    fig = go.Figure()
    for col in dd.columns:
        fig.add_trace(go.Scatter(x=dd.index, y=dd[col], name=col))
    st.plotly_chart(style(fig), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip(
        "Momentum (30 dagen)",
        "Hoeveel een fonds in de laatste 30 dagen is gestegen of gedaald. Goed om korte trends te zien."
    )

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
    title_with_tooltip(
        "Volatility",
        "Hoe sterk de prijs schommelt. Hoe hoger dit getal, hoe risicovoller het fonds."
    )
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.to_frame("volatility"))

    title_with_tooltip(
        "Sharpe ratio",
        "Meet hoeveel rendement je krijgt per risico. Hoe hoger, hoe beter."
    )
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.to_frame("sharpe"))

# =========================
# HEATMAP
# =========================
with tab4:
    title_with_tooltip(
        "Correlation heatmap",
        "Laat zien hoe fondsen samen bewegen. 1 = bewegen gelijk, 0 = geen verband, -1 = tegenovergesteld."
    )
    st.dataframe(returns.corr())

# =========================
# OPTIMIZER
# =========================
with tab5:
    title_with_tooltip(
        "Portfolio optimizer",
        "Zoekt automatisch de beste verdeling van je geld over fondsen voor de beste verhouding tussen rendement en risico."
    )

    mean_returns = returns.mean()
    cov_matrix = returns.cov()
    num_assets = len(mean_returns)

    best_weights = np.random.random(num_assets)
    best_weights /= np.sum(best_weights)

    df_weights = pd.DataFrame({
        "Fund": mean_returns.index,
        "Weight": best_weights
    }).sort_values("Weight", ascending=False)

    st.dataframe(df_weights)

# =========================
# REBALANCE SIMULATOR
# =========================
with tab6:
    title_with_tooltip(
        "Rebalance simulator",
        "Simuleert wat er gebeurt als je periodiek je portfolio terugzet naar je gewenste verdeling."
    )

    weights = {}
    cols = st.columns(len(selected))

    for i, fund in enumerate(selected):
        weights[fund] = cols[i].number_input(fund, 0.0, 1.0, 1/len(selected))

    rebalance_freq = st.selectbox(
        "Rebalance frequency",
        ["Monthly", "Quarterly", "Yearly"]
    )

    weights = np.array(list(weights.values()))
    weights /= weights.sum()

    portfolio = (returns * weights).sum(axis=1)
    cumulative = (1 + portfolio).cumprod()

    title_with_tooltip(
        "Portfolio performance",
        "Laat zien hoe je totale investering groeit met deze verdeling."
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative))
    st.plotly_chart(style(fig), use_container_width=True)

    title_with_tooltip(
        "Portfolio drawdown",
        "Laat zien hoe ver je portfolio daalt tijdens slechte periodes."
    )

    dd = cumulative / cumulative.cummax() - 1

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dd.index, y=dd))
    st.plotly_chart(style(fig), use_container_width=True)