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
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.warning("Geen data beschikbaar")
    st.stop()

# =========================
# PIVOT
# =========================
pivot = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot.columns)

# =========================
# STATE
# =========================
if "selected_funds" not in st.session_state:
    st.session_state.selected_funds = all_funds[:5]

col1, col2 = st.columns(2)

with col1:
    if st.button("✅ Selecteer alles"):
        st.session_state.selected_funds = all_funds

with col2:
    if st.button("❌ Deselecteer alles"):
        st.session_state.selected_funds = []

selected = st.multiselect("Selecteer fondsen", all_funds, key="selected_funds")

if len(selected) == 0:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot[selected]

# =========================
# PERFORMANCE
# =========================
pct = (pivot / pivot.iloc[0] - 1) * 100

st.subheader("📈 Groei (%)")
st.line_chart(pct)

# =========================
# MOMENTUM (FIXED)
# =========================
st.subheader("⚡ Momentum (30 dagen)")

momentum = (pivot / pivot.shift(30) - 1) * 100
momentum_last = momentum.iloc[-1].dropna()

if not momentum_last.empty:
    st.bar_chart(momentum_last.sort_values(ascending=False))
else:
    st.info("Niet genoeg data voor momentum")

# =========================
# HEATMAP (FIXED COLORS)
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

# 🎨 KLEUR FUNCTIE
def color(val, col):
    if pd.isna(val):
        return "background-color:#111;color:#666"

    short = ["1D","3D","1W","2W"]

    if col in short:
        if val < -0.01: return "background:#ff0000;color:white"
        elif val < 0: return "background:#f4a261"
        elif val < 0.25: return "background:#ffcc00"
        elif val < 0.5: return "background:#a8d08d"
        elif val < 0.75: return "background:#70ad47"
        else: return "background:#548235;color:white"
    else:
        if val < -0.01: return "background:#ff0000;color:white"
        elif val < 2.5: return "background:#f4a261"
        elif val < 4: return "background:#ffcc00"
        elif val < 10: return "background:#a8d08d"
        elif val < 25: return "background:#70ad47"
        else: return "background:#548235;color:white"

styled = heatmap.style.format("{:.2f}%")

for c in heatmap.columns:
    styled = styled.apply(lambda s: [color(v, c) for v in s], subset=[c])

st.dataframe(styled, use_container_width=True)

# =========================
# ADVANCED ANALYTICS
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
st.subheader("🏆 Sharpe")
sharpe = returns.mean() / returns.std()
st.dataframe(sharpe.sort_values(ascending=False).to_frame())

# =========================
# GLOBAL PERFORMANCE
# =========================
st.divider()
st.header("🌍 Markt overzicht")

full = df.pivot(index="date", columns="fund", values="price")
full_pct = (full / full.iloc[0] - 1) * 100
perf = full_pct.iloc[-1].dropna()

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Beste fondsen")
    st.bar_chart(perf.sort_values(ascending=False).head(10))

with col2:
    st.subheader("📉 Slechtste fondsen")
    st.bar_chart(perf.sort_values().head(10))
