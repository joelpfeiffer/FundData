import streamlit as st
import pandas as pd
import numpy as np
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

# =========================
# REFRESH
# =========================
if st.button("🔄 Refresh data"):
    st.cache_data.clear()

# =========================
# DATA LADEN
# =========================
@st.cache_data(ttl=60)
def load_data():
    url = f"{CSV_URL}?t={int(time.time())}"
    df = pd.read_csv(url)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df

df = load_data()

if df.empty:
    st.warning("Geen data beschikbaar")
    st.stop()

# =========================
# DATA PREP
# =========================
pivot = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot.columns)

# =========================
# STATE INIT
# =========================
if "selected_funds" not in st.session_state:
    st.session_state.selected_funds = all_funds[:5]

# =========================
# SELECTIE KNOPPEN
# =========================
col1, col2 = st.columns(2)

with col1:
    if st.button("✅ Selecteer alles"):
        st.session_state.selected_funds = all_funds

with col2:
    if st.button("❌ Deselecteer alles"):
        st.session_state.selected_funds = []

# =========================
# MULTISELECT (STABLE)
# =========================
selected = st.multiselect(
    "Selecteer fondsen",
    all_funds,
    key="selected_funds"
)

st.caption(f"{len(selected)} fondsen geselecteerd")

if len(selected) == 0:
    st.info("👆 Selecteer minimaal één fonds")
    st.stop()

pivot = pivot[selected]

# =========================
# GROEI
# =========================
norm = pivot / pivot.iloc[0]
pct = (norm - 1) * 100

st.subheader("📈 Groei (%)")
st.line_chart(pct)

# =========================
# ACTUELE WAARDES
# =========================
latest = df.groupby("fund").last().reset_index()
latest = latest[latest["fund"].isin(selected)]

st.subheader("📊 Actuele waardes")
st.dataframe(latest, use_container_width=True)

# =========================
# METRICS
# =========================
perf = pct.iloc[-1].dropna()

col1, col2 = st.columns(2)

with col1:
    st.metric("🏆 Beste", perf.idxmax(), f"{perf.max():.2f}%")

with col2:
    st.metric("📉 Slechtste", perf.idxmin(), f"{perf.min():.2f}%")

# =========================
# HEATMAP
# =========================
st.subheader("🔥 Rendement Heatmap")

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

styled = heatmap.style.format(lambda x: f"{x:.2f}%" if pd.notna(x) else "")

st.dataframe(styled, use_container_width=True)

# =========================
# 🧠 ADVANCED ANALYTICS
# =========================
st.divider()
st.header("🧠 Advanced Analytics")

returns = pivot.pct_change().dropna()

# Drawdown
st.subheader("📉 Drawdown")
drawdown = (pivot / pivot.cummax() - 1) * 100
st.line_chart(drawdown)

# Volatility
st.subheader("⚖️ Volatility")
vol = returns.std() * np.sqrt(252)
st.dataframe(vol.sort_values(ascending=False).to_frame())

# Sharpe
st.subheader("🏆 Sharpe Ratio")
sharpe = returns.mean() / returns.std()
st.dataframe(sharpe.sort_values(ascending=False).to_frame())

# Momentum
st.subheader("⚡ Momentum (30d)")
momentum = (pivot / pivot.shift(30) - 1) * 100
st.bar_chart(momentum.iloc[-1])

# Correlation
st.subheader("🔗 Correlation")
st.dataframe(returns.corr())

# Portfolio
st.subheader("💼 Portfolio")
weights = np.repeat(1/len(selected), len(selected))
portfolio = (returns * weights).sum(axis=1)
st.line_chart((1+portfolio).cumprod())

# =========================
# 🌍 GLOBAL
# =========================
st.divider()
st.header("🌍 Markt overzicht")

full = df.pivot(index="date", columns="fund", values="price")
full_pct = (full / full.iloc[0] - 1) * 100
perf = full_pct.iloc[-1].dropna().sort_values()

col1, col2 = st.columns(2)

with col1:
    st.bar_chart(perf.tail(10))

with col2:
    st.bar_chart(perf.head(10))
