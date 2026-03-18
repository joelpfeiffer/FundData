import streamlit as st
import pandas as pd
import numpy as np
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

st.set_page_config(layout="wide", page_title="Funds Terminal")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
html, body {
    font-family: Inter, sans-serif;
}
.block-container {
    padding-top: 1.5rem;
}
[data-testid="metric-container"] {
    background: #111827;
    border-radius: 10px;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)

st.title("Funds Intelligence Terminal")

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load()

pivot = df.pivot(index="date", columns="fund", values="price")
returns = pivot.pct_change().dropna()

all_funds = list(pivot.columns)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Portfolio")

selected = st.sidebar.multiselect(
    "Funds",
    all_funds,
    default=all_funds[:5]
)

if not selected:
    st.warning("Select at least one fund")
    st.stop()

pivot = pivot[selected]
returns = pivot.pct_change().dropna()

# =========================
# KPI
# =========================
perf = (pivot / pivot.iloc[0] - 1).iloc[-1] * 100

col1, col2, col3 = st.columns(3)

col1.metric("Best fund", perf.idxmax(), f"{perf.max():.2f}%")
col2.metric("Worst fund", perf.idxmin(), f"{perf.min():.2f}%")
col3.metric("Avg return", "", f"{perf.mean():.2f}%")

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Momentum", "Risk", "Portfolio", "Correlation"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    st.subheader("Normalized performance")
    norm = pivot / pivot.iloc[0]
    st.line_chart(norm)

    st.subheader("Drawdown")
    dd = norm / norm.cummax() - 1
    st.line_chart(dd)

# =========================
# MOMENTUM
# =========================
with tab2:
    st.subheader("30-day momentum")
    mom30 = (pivot / pivot.shift(30) - 1) * 100
    st.bar_chart(mom30.iloc[-1].dropna())

    st.subheader("90-day momentum")
    mom90 = (pivot / pivot.shift(90) - 1) * 100
    st.bar_chart(mom90.iloc[-1].dropna())

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Volatility (annualized)")
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.sort_values(ascending=False).to_frame("vol"))

    st.subheader("Sharpe ratio")
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

    st.subheader("Rolling volatility (30d)")
    rolling_vol = returns.rolling(30).std() * np.sqrt(252)
    st.line_chart(rolling_vol)

# =========================
# PORTFOLIO SIMULATOR
# =========================
with tab4:
    st.subheader("Portfolio allocation")

    weights = {}
    cols = st.columns(len(selected))

    for i, fund in enumerate(selected):
        weights[fund] = cols[i].number_input(
            fund, min_value=0.0, max_value=1.0, value=1/len(selected)
        )

    total_weight = sum(weights.values())

    if total_weight == 0:
        st.warning("Weights must be > 0")
    else:
        weights = {k: v/total_weight for k,v in weights.items()}

        portfolio_returns = returns.copy()
        for fund in selected:
            portfolio_returns[fund] *= weights[fund]

        portfolio = portfolio_returns.sum(axis=1)

        st.subheader("Portfolio performance")
        st.line_chart((1 + portfolio).cumprod())

        st.subheader("Portfolio drawdown")
        cum = (1 + portfolio).cumprod()
        dd = cum / cum.cummax() - 1
        st.line_chart(dd)

# =========================
# CORRELATION
# =========================
with tab5:
    st.subheader("Correlation matrix")

    corr = returns.corr()

    def color(val):
        if val > 0.7:
            return "background-color:#70ad47;color:white"
        elif val > 0.3:
            return "background-color:#a9d18e;color:black"
        elif val > 0:
            return "background-color:#ffd966;color:black"
        else:
            return "background-color:#ff4d4d;color:white"

    styled = corr.style.applymap(color).format("{:.2f}")
    st.write(styled)

# =========================
# SMART INSIGHTS
# =========================
st.subheader("Insights")

col1, col2, col3 = st.columns(3)

# momentum
mom = (pivot / pivot.shift(30) - 1).iloc[-1]
col1.metric("Best momentum", mom.idxmax(), f"{mom.max()*100:.2f}%")

# risk
vol = returns.std()
col2.metric("Lowest risk", vol.idxmin(), f"{vol.min():.4f}")

# consistency
consistency = returns.std()
col3.metric("Most stable", consistency.idxmin(), "")
