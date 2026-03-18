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
# STYLE
# =========================
def style(fig, y_label):
    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title=y_label
    )
    fig.update_xaxes(showspikes=True)
    return fig

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "price", "fund"])
    return df.sort_values("date")

df = load()

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
selected = st.sidebar.multiselect("Funds", all_funds, default=all_funds[:5])

if not selected:
    st.stop()

pivot = pivot_full[selected]

# =========================
# TIMEFRAME
# =========================
mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]

else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

returns = pivot.pct_change().dropna()
returns_full = pivot_full[selected].pct_change().dropna()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# HEATMAP (CUSTOM COLORS)
# =========================
with tab4:
    st.subheader("Return heatmap")

    df_full = pivot_full[selected]
    latest_date = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,
        "6M":180,"1Y":365,"2Y":730,"5Y":1825
    }

    def calc_return(days):
        past_date = latest_date - pd.Timedelta(days=days)
        past_df = df_full[df_full.index <= past_date]

        if past_df.empty:
            return pd.Series(index=df_full.columns, dtype=float)

        return (df_full.loc[latest_date] / past_df.iloc[-1] - 1) * 100

    heatmap = pd.DataFrame({
        name: calc_return(days)
        for name, days in periods.items()
    }).round(2)

    # =========================
    # SPLIT SHORT / LONG TERM
    # =========================
    short_cols = ["1D","2D","3D","4D","1W","2W","3W"]
    long_cols = [c for c in heatmap.columns if c not in short_cols]

    heat_short = heatmap[short_cols]
    heat_long = heatmap[long_cols]

    # =========================
    # SHORT TERM (SUBTLE COLORS)
    # =========================
    fig1 = go.Figure(data=go.Heatmap(
        z=heat_short.values,
        x=heat_short.columns,
        y=heat_short.index,
        colorscale=[
            [0, "#ffcccc"],
            [0.5, "#ffffff"],
            [1, "#ccffcc"]
        ],
        zmid=0,
        text=heat_short.astype(str) + "%",
        texttemplate="%{text}"
    ))

    fig1.update_layout(
        title="Short term (<1M)",
        xaxis_title="Period",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig1, use_container_width=True)

    # =========================
    # LONG TERM (STRONG COLORS)
    # =========================
    fig2 = go.Figure(data=go.Heatmap(
        z=heat_long.values,
        x=heat_long.columns,
        y=heat_long.index,
        colorscale="RdYlGn",
        zmid=0,
        text=heat_long.astype(str) + "%",
        texttemplate="%{text}"
    ))

    fig2.update_layout(
        title="Long term (≥1M)",
        xaxis_title="Period",
        yaxis_title="Fund"
    )

    st.plotly_chart(fig2, use_container_width=True)