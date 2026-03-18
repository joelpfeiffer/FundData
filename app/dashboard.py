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
# PREP
# =========================
pivot = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot.columns)

# =========================
# STATE FIX
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

if not selected:
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
# MOMENTUM (SAFE)
# =========================
st.subheader("⚡ Momentum (30 dagen)")

momentum = (pivot / pivot.shift(30) - 1) * 100
momentum_last = momentum.iloc[-1].dropna()

if len(momentum_last) > 0:
    st.bar_chart(momentum_last.sort_values(ascending=False).to_frame("momentum"))
else:
    st.info("Niet genoeg data voor momentum")

# =========================
# HEATMAP (WERKEND)
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

def color(val):
    if pd.isna(val):
        return ""
    if val < 0:
        return "background-color:#ff4d4d;color:white"
    elif val < 1:
        return "background-color:#ffd966"
    elif val < 5:
        return "background-color:#a9d18e"
    else:
        return "background-color:#70ad47;color:white"

styled = heatmap.style.format("{:.2f}%").applymap(color)

st.write(styled)

# =========================
# ANALYTICS
# =========================
st.header("🧠 Advanced Analytics")

returns = pivot.pct_change().dropna()

# Drawdown
st.subheader("📉 Drawdown")
drawdown = (pivot / pivot.cummax() - 1) * 100
st.line_chart(drawdown)

# Volatility
st.subheader("⚖️ Volatility")
vol = returns.std() * np.sqrt(252)
st.dataframe(vol.sort_values(ascending=False).to_frame("volatility"))

# Sharpe
st.subheader("🏆 Sharpe Ratio")
sharpe = returns.mean() / returns.std()
st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

# =========================
# GLOBAL MARKET (FIXED)
# =========================
st.header("🌍 Markt overzicht")

full = df.pivot(index="date", columns="fund", values="price")
perf = (full / full.iloc[0] - 1).iloc[-1] * 100
perf = perf.dropna()

if len(perf) > 0:

    top = perf.sort_values(ascending=False).head(10).to_frame("performance")
    worst = perf.sort_values().head(10).to_frame("performance")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Beste fondsen")
        st.bar_chart(top)

    with col2:
        st.subheader("📉 Slechtste fondsen")
        st.bar_chart(worst)

else:
    st.info("Geen marktdata beschikbaar")
