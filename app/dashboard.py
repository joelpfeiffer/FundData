import streamlit as st
import pandas as pd
import numpy as np
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

st.set_page_config(layout="wide", page_title="Funds Dashboard")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
h1, h2, h3 {
    font-weight: 600;
}
.block-container {
    padding-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

st.title("Funds Intelligence Dashboard")

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.warning("No data available")
    st.stop()

# =========================
# PREP
# =========================
pivot = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot.columns)

# =========================
# SIDEBAR FILTERS
# =========================
st.sidebar.header("Filters")

if "selected_funds" not in st.session_state:
    st.session_state.selected_funds = all_funds[:5]

if st.sidebar.button("Select all"):
    st.session_state.selected_funds = all_funds

if st.sidebar.button("Clear selection"):
    st.session_state.selected_funds = []

selected = st.sidebar.multiselect(
    "Funds",
    all_funds,
    key="selected_funds"
)

if not selected:
    st.warning("Please select at least one fund")
    st.stop()

pivot = pivot[selected]

# =========================
# PERFORMANCE
# =========================
pct = (pivot / pivot.iloc[0] - 1) * 100

st.subheader("Performance (%)")
st.line_chart(pct)

# =========================
# METRICS
# =========================
perf = pct.iloc[-1].dropna()

col1, col2 = st.columns(2)

with col1:
    st.metric("Best performing fund", perf.idxmax(), f"{perf.max():.2f}%")

with col2:
    st.metric("Worst performing fund", perf.idxmin(), f"{perf.min():.2f}%")

# =========================
# MOMENTUM
# =========================
st.subheader("Momentum (30 days)")

momentum = (pivot / pivot.shift(30) - 1) * 100
momentum_last = momentum.iloc[-1].dropna()

if len(momentum_last) > 0:
    st.bar_chart(momentum_last.sort_values(ascending=False).to_frame("momentum"))
else:
    st.info("Not enough data")

# =========================
# HEATMAP (PRO + CONTRAST)
# =========================
st.subheader("Return heatmap")

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

# 🎨 CONTRAST KLEUREN
def color(val):
    if pd.isna(val):
        return ""

    if val < 0:
        return "background-color:#ff4d4d;color:white"

    elif val < 0.5:
        return "background-color:#ffd966;color:black"

    elif val < 2:
        return "background-color:#a9d18e;color:black"

    else:
        return "background-color:#70ad47;color:white"

styled = (
    heatmap.style
    .format("{:.2f}%")
    .applymap(color)
    .set_properties(**{
        "text-align": "center",
        "font-weight": "600"
    })
)

st.write(styled)

# =========================
# ANALYTICS
# =========================
st.subheader("Risk & analytics")

returns = pivot.pct_change().dropna()

# Drawdown
st.write("Drawdown")
drawdown = (pivot / pivot.cummax() - 1) * 100
st.line_chart(drawdown)

# Volatility
st.write("Volatility")
vol = returns.std() * np.sqrt(252)
st.dataframe(vol.sort_values(ascending=False).to_frame("volatility"))

# Sharpe
st.write("Sharpe ratio")
sharpe = returns.mean() / returns.std()
st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

# =========================
# GLOBAL MARKET
# =========================
st.subheader("Market overview")

full = df.pivot(index="date", columns="fund", values="price")
perf_all = (full / full.iloc[0] - 1).iloc[-1] * 100
perf_all = perf_all.dropna()

if len(perf_all) > 0:

    top = perf_all.sort_values(ascending=False).head(10).to_frame("performance")
    worst = perf_all.sort_values().head(10).to_frame("performance")

    col1, col2 = st.columns(2)

    with col1:
        st.write("Top performers")
        st.bar_chart(top)

    with col2:
        st.write("Worst performers")
        st.bar_chart(worst)

else:
    st.info("No market data available")
