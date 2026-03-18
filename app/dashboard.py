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
# TOOLTIP HELPER
# =========================
def title_with_tooltip(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

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

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filters")

selected = st.sidebar.multiselect(
    "Funds",
    all_funds,
    default=all_funds[:5]
)

timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["1M", "3M", "6M", "1Y", "3Y", "ALL"]
)

if not selected:
    st.warning("Select at least one fund")
    st.stop()

pivot = pivot_full[selected]

# =========================
# TIMEFRAME FILTER
# =========================
end_date = pivot.index.max()

if timeframe != "ALL":
    days_map = {
        "1M":30,
        "3M":90,
        "6M":180,
        "1Y":365,
        "3Y":1095
    }
    start_date = end_date - pd.Timedelta(days=days_map[timeframe])
    pivot = pivot[pivot.index >= start_date]

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
# OVERVIEW (INTERACTIVE)
# =========================
with tab1:

    # PRICE CHART
    title_with_tooltip(
        "Fund prices",
        "Absolute prijs van fondsen (echte waarde)"
    )

    fig_price = go.Figure()

    for col in pivot.columns:
        fig_price.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            mode='lines',
            name=col
        ))

    fig_price.update_layout(height=400)
    st.plotly_chart(fig_price, use_container_width=True)

    # NORMALIZED PERFORMANCE
    title_with_tooltip(
        "Normalized performance",
        "Alle fondsen starten op 1 (relatieve groei)"
    )

    norm = pivot / pivot.iloc[0]

    fig_norm = go.Figure()

    for col in norm.columns:
        fig_norm.add_trace(go.Scatter(
            x=norm.index,
            y=norm[col],
            mode='lines',
            name=col
        ))

    fig_norm.update_layout(height=400)
    st.plotly_chart(fig_norm, use_container_width=True)

    # DRAWDOWN
    title_with_tooltip(
        "Drawdown",
        "Daling vanaf hoogste punt (risico indicator)"
    )

    dd = norm / norm.cummax() - 1

    fig_dd = go.Figure()

    for col in dd.columns:
        fig_dd.add_trace(go.Scatter(
            x=dd.index,
            y=dd[col],
            mode='lines',
            name=col
        ))

    fig_dd.update_layout(height=400)
    st.plotly_chart(fig_dd, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip(
        "Momentum (30 dagen)",
        "Rendement laatste 30 dagen"
    )

    mom = (pivot / pivot.shift(30) - 1) * 100
    st.bar_chart(mom.iloc[-1].dropna())

# =========================
# RISK
# =========================
with tab3:
    title_with_tooltip(
        "Volatility",
        "Hoeveel een fonds fluctueert"
    )

    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.sort_values(ascending=False))

    title_with_tooltip(
        "Sharpe ratio",
        "Rendement per risico"
    )

    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.sort_values(ascending=False))

# =========================
# HEATMAP (INTERACTIVE + CONTRAST)
# =========================
with tab4:
    title_with_tooltip(
        "Return heatmap",
        "Groen = positief, rood = negatief rendement"
    )

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

    z = heatmap.values
    x = heatmap.columns
    y = heatmap.index

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=x,
        y=y,
        colorscale=[
            [0, "#ff4d4d"],
            [0.5, "#ffd966"],
            [1, "#70ad47"]
        ],
        colorbar=dict(title="Return %")
    ))

    # TEXT + CONTRAST
    for i in range(len(y)):
        for j in range(len(x)):
            val = z[i][j]

            if pd.isna(val):
                text = ""
                color = "gray"
            else:
                text = f"{val:.2f}%"
                color = "white" if val < 0 or val > 5 else "black"

            fig.add_annotation(
                x=x[j],
                y=y[i],
                text=text,
                showarrow=False,
                font=dict(color=color, size=12)
            )

    fig.update_layout(height=600)

    st.plotly_chart(fig, use_container_width=True)
