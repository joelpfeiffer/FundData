import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

# =========================
# DATA LOADING (FIXED)
# =========================
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(CSV_URL)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "price", "fund"])
        return df.sort_values("date")
    except Exception as e:
        st.error(f"Fout bij laden data: {e}")
        return pd.DataFrame()

st.title("📊 Fund Dashboard")

df = load_data()

st.write("Debug DF:", df.shape)

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
st.sidebar.title("Instellingen")
funds = list(pivot_full.columns)
selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])
mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected].copy()
pivot = pivot.sort_index()

# =========================
# FILTERS (FIXED SAFE)
# =========================
if mode == "Preset":
    tf = st.sidebar.selectbox("Periode", ["1W", "2W", "1M", "3M", "6M", "1Y", "ALL"])
    days_map = {"1W": 7, "2W": 14, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}

    if tf != "ALL" and not pivot.empty:
        cutoff = pivot.index.max() - pd.Timedelta(days=days_map[tf])
        pivot = pivot[pivot.index >= cutoff]

else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

# =========================
# CLEAN DATA (FIXED)
# =========================
pivot = pivot.dropna(how="all")
pivot = pivot.fillna(method="ffill")

st.write("Debug Pivot:", pivot.shape)

if pivot.empty or len(pivot) < 2:
    st.warning("Te weinig data na filtering")
    st.dataframe(df)
    st.stop()

returns = pivot.pct_change().dropna()

st.write("Debug Returns:", returns.shape)

if returns.empty:
    st.warning("Geen returns beschikbaar")
    st.dataframe(pivot)
    st.stop()

# =========================
# CALCULATIONS
# =========================
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean() * TRADING_DAYS) / vol.replace(0, np.nan)

drawdown = pivot / pivot.cummax() - 1
max_dd = drawdown.min()

# =========================
# TABS (ALL FILLED)
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview", "Performance", "Risk", "Heatmap", "Optimizer", "Rebalance", "Raw Data"
])

# =========================
# TAB 1 OVERVIEW
# =========================
with tab1:
    st.subheader("Overview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
    c2.metric("Volatiliteit", f"{vol.mean():.2f}")
    c3.metric("Sharpe", f"{sharpe.mean():.2f}")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# TAB 2 PERFORMANCE
# =========================
with tab2:
    st.subheader("Performance per fonds")
    st.dataframe(ret.sort_values(ascending=False))

# =========================
# TAB 3 RISK
# =========================
with tab3:
    st.subheader("Risico metrics")
    risk_df = pd.DataFrame({
        "Volatiliteit": vol,
        "Max Drawdown": max_dd,
        "Sharpe": sharpe
    })
    st.dataframe(risk_df)

# =========================
# TAB 4 HEATMAP
# =========================
with tab4:
    st.subheader("Correlatie heatmap")
    corr = returns.corr()
    st.dataframe(corr)

# =========================
# TAB 5 OPTIMIZER (BASIC)
# =========================
with tab5:
    st.subheader("Simple optimizer (gelijke weging)")
    weights = np.repeat(1/len(pivot.columns), len(pivot.columns))
    st.write(dict(zip(pivot.columns, weights)))

# =========================
# TAB 6 REBALANCE
# =========================
with tab6:
    st.subheader("Rebalance voorbeeld")
    st.write("Herbalanceer maandelijks (demo)")

# =========================
# TAB 7 RAW DATA (FIXED MAIN ISSUE)
# =========================
with tab7:
    st.subheader("Raw Data")
    st.dataframe(df)
    st.subheader("Pivot Data")
    st.dataframe(pivot)
