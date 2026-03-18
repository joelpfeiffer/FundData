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
# HELPER: TOOLTIP TITLE
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
    title_with_tooltip(
        "Normalized performance",
        "Alle fondsen starten op 1. Hiermee vergelijk je relatieve groei."
    )
    norm = pivot / pivot.iloc[0]
    st.line_chart(norm)

    title_with_tooltip(
        "Drawdown",
        "Laat zien hoeveel een fonds vanaf de piek is gedaald."
    )
    dd = norm / norm.cummax() - 1
    st.line_chart(dd)

# =========================
# PERFORMANCE
# =========================
with tab2:
    title_with_tooltip(
        "Momentum (30 dagen)",
        "Percentage verandering over de laatste 30 dagen."
    )
    mom = (pivot / pivot.shift(30) - 1) * 100
    st.bar_chart(mom.iloc[-1].dropna().to_frame("momentum"))

# =========================
# RISK
# =========================
with tab3:
    title_with_tooltip(
        "Volatility",
        "Hoe sterk de koers schommelt. Hoger = meer risico."
    )
    vol = returns.std() * np.sqrt(252)
    st.dataframe(vol.sort_values(ascending=False).to_frame("volatility"))

    title_with_tooltip(
        "Sharpe ratio",
        "Rendement per eenheid risico. Hoger = beter."
    )
    sharpe = returns.mean() / returns.std()
    st.dataframe(sharpe.sort_values(ascending=False).to_frame("sharpe"))

# =========================
# 🔥 HEATMAP (INTERACTIVE + CONTRAST)
# =========================
with tab4:
    title_with_tooltip(
        "Return heatmap",
        "Toont rendement per periode. Groen = positief, rood = negatief."
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

    # TEXT COLORS
    text_colors = []
    for row in z:
        row_colors = []
        for val in row:
            if pd.isna(val):
                row_colors.append("gray")
            elif val < 0:
                row_colors.append("white")
            elif val < 1:
                row_colors.append("black")
            elif val < 5:
                row_colors.append("black")
            else:
                row_colors.append("white")
        text_colors.append(row_colors)

    text = [[f"{v:.2f}%" if pd.notna(v) else "" for v in row] for row in z]

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

    # TEXT LAYER
    for i in range(len(y)):
        for j in range(len(x)):
            fig.add_annotation(
                x=x[j],
                y=y[i],
                text=text[i][j],
                showarrow=False,
                font=dict(color=text_colors[i][j], size=12)
            )

    fig.update_layout(height=600)

    st.plotly_chart(fig, use_container_width=True)
