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
# TOOLTIP HELPER
# =========================
def section_title(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

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

if df.empty:
    st.error("No data loaded")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
all_funds = list(pivot_full.columns)

# =========================
# SIDEBAR
# =========================
selected = st.sidebar.multiselect("Funds", all_funds, default=all_funds[:5])

if not selected:
    st.stop()

pivot = pivot_full[selected]

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

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    section_title(
        "Fund Prices",
        "Toont de werkelijke prijs van elk fonds over tijd. Gebruik dit om absolute waarde te zien."
    )

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(style(fig,"Price (€)"), use_container_width=True)

    section_title(
        "Normalized Performance",
        "Alle fondsen starten op dezelfde waarde (1). Hierdoor zie je welke beter presteert."
    )

    norm = pivot / pivot.iloc[0]
    fig = go.Figure()
    for col in norm.columns:
        fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(style(fig,"Index"), use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section_title(
        "Momentum",
        "Laat zien hoeveel een fonds recent is gestegen of gedaald. Handig om trends te herkennen."
    )

    shift = 30 if len(pivot) > 30 else max(1, int(len(pivot)/2))
    mom = (pivot / pivot.shift(shift) - 1) * 100
    last = mom.iloc[-1].dropna()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=last.index, y=last.values))
    fig.update_layout(xaxis_title="Fund", yaxis_title="Return (%)")
    st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    section_title(
        "Volatility",
        "Hoe sterk een fonds schommelt. Hoger = meer risico."
    )
    st.dataframe((returns.std()*np.sqrt(TRADING_DAYS)).to_frame("Volatility"))

    section_title(
        "Sharpe Ratio",
        "Meet rendement per risico. Hoger betekent efficiënter."
    )
    st.dataframe((returns.mean()/returns.std()).to_frame("Sharpe"))

# =========================
# HEATMAP
# =========================
with tab4:
    section_title(
        "Return Heatmap",
        "Elke cel toont het rendement (%) over een periode. Groen = winst, rood = verlies."
    )

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {"1D":1,"1W":7,"1M":30,"3M":90,"1Y":365}

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k:calc(v) for k,v in periods.items()}).round(2)

    fig = go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns,
        y=heatmap.index,
        colorscale="RdYlGn",
        zmid=0,
        text=heatmap.astype(str)+"%",
        texttemplate="%{text}"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    section_title(
        "Portfolio Optimizer",
        "Zoekt de beste verdeling voor maximale verhouding tussen rendement en risico."
    )

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({"Fund":selected,"Weight":w}))

# =========================
# REBALANCE
# =========================
with tab6:
    section_title(
        "Rebalance Simulator",
        "Simuleert hoe je investering groeit bij verschillende verdelingen."
    )

    st.warning("Geen financieel advies")

    capital = st.number_input("Start (€)",100,1000000,10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)
    value = capital*(1+port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=value.index,y=value))
    st.plotly_chart(style(fig,"Portfolio (€)"), use_container_width=True)