import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide", page_title="Funds Terminal")

# =========================
# TOOLTIP
# =========================
def title(t, tip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(t)
    with col2:
        st.markdown(f"<span title='{tip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

if df.empty:
    st.error("Geen data")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected]

# =========================
# RETURNS
# =========================
returns = pivot.pct_change().replace([np.inf, -np.inf], np.nan).dropna(how="all")

if returns.empty:
    st.error("Geen returns data")
    st.stop()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview","Performance","Risk","Heatmap"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    title("Prijsontwikkeling", "Prijs per fonds")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE (FIXED)
# =========================
with tab2:
    title("Momentum", "Laatste % verandering")

    shift = min(30, len(pivot)-1)

    mom = (pivot / pivot.shift(shift) - 1) * 100
    last = mom.iloc[-1].replace([np.inf,-np.inf],np.nan).dropna()

    if last.empty:
        st.warning("Geen momentum data")
    else:
        fig = go.Figure(go.Bar(
            x=last.index,
            y=last.values
        ))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    title("Volatility", "Risico (schommelingen)")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

# =========================
# HEATMAP (FIXED)
# =========================
with tab4:

    title("Heatmap", "Rendement per periode")

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"1W":7,"1M":30,
        "3M":90,"6M":180,"1Y":365
    }

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({
        k: calc(v) for k,v in periods.items()
    }).replace([np.inf,-np.inf],np.nan)

    heatmap = heatmap.dropna(how="all")

    if heatmap.empty:
        st.warning("Geen heatmap data")
    else:
        fig = go.Figure(data=go.Heatmap(
            z=heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            colorscale="RdYlGn",
            zmid=0,
            text=heatmap.round(2).astype(str)+"%",
            texttemplate="%{text}"
        ))

        st.plotly_chart(fig, use_container_width=True)