import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
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

if df.empty:
    st.warning("No data available")
    st.stop()

pivot = df.pivot(index="date", columns="fund", values="price")
returns = pivot.pct_change().dropna()

all_funds = list(pivot.columns)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Portfolio")

if "selected_funds" not in st.session_state:
    st.session_state.selected_funds = all_funds[:5]

if st.sidebar.button("Select all"):
    st.session_state.selected_funds = all_funds

if st.sidebar.button("Clear"):
    st.session_state.selected_funds = []

selected = st.sidebar.multiselect(
    "Funds",
    all_funds,
    key="selected_funds"
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
col3.metric("Average return", "", f"{perf.mean():.2f}%")

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap"
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
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum (30 days)")
    mom = (pivot / pivot.shift(30) - 1) * 100
    st.bar_chart(mom.iloc[-1].dropna().to_frame("momentum"))

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Volatility")
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.sort_values(ascending=False).to_frame("volatility"))

    st.subheader("Sharpe ratio")
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

# =========================
# 🔥 INTERACTIVE HEATMAP
# =========================
with tab4:
    st.subheader("Return heatmap (interactive)")

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

    # 👉 Plotly heatmap (PRO)
    fig = px.imshow(
        heatmap,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale=[
            [0, "#ff4d4d"],   # red
            [0.5, "#ffd966"], # yellow
            [1, "#70ad47"]    # green
        ]
    )

    fig.update_layout(
        coloraxis_colorbar_title="Return %",
        xaxis_title="Period",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig, use_container_width=True)
