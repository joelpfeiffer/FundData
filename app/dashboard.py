import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide")

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load()
pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

pivot = pivot_full[selected]

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

    st.subheader("Prijsontwikkeling")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Genormaliseerde groei (%)")

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))
    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader("Momentum (%)")

    if len(pivot) > 1:
        shift = min(30, len(pivot)-1)
        mom = (pivot / pivot.shift(shift) - 1) * 100
        last = mom.iloc[-1].dropna()

        if not last.empty:
            df_plot = last.sort_values(ascending=False)

            fig = go.Figure(go.Bar(
                x=df_plot.index,
                y=df_plot.values
            ))

            st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Volatility")
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    st.subheader("Sharpe Ratio")
    sharpe = (returns.mean()*TRADING_DAYS)/vol
    st.dataframe(sharpe.to_frame("Sharpe"))

    st.subheader("Correlatie (Fund vergelijking)")
    corr = returns.corr()

    fig = px.imshow(corr, text_auto=True, color_continuous_scale="RdYlGn")
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP (FIXED COLORS)
# =========================
with tab4:

    st.subheader("Rendement Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"2D":2,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,
        "1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()})
    heatmap = heatmap.loc[selected]

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

# =========================
# OPTIMIZER
# =========================
with tab5:

    st.subheader("Portfolio gewichten (voorbeeld)")

    w = np.random.random(len(selected))
    w /= w.sum()

    df_opt = pd.DataFrame({
        "Fund": selected,
        "Weight (%)": (w*100).round(2)
    })

    st.dataframe(df_opt)

# =========================
# REBALANCE
# =========================
with tab6:

    st.subheader("Portfolio verdeling (%)")

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    if "alloc" not in st.session_state:
        st.session_state.alloc = {f: int(100/len(selected)) for f in selected}

    # sync
    st.session_state.alloc = {
        k: v for k, v in st.session_state.alloc.items() if k in selected
    }

    for f in selected:
        if f not in st.session_state.alloc:
            st.session_state.alloc[f] = 0

    cols = st.columns(len(selected))

    for i, f in enumerate(selected):
        with cols[i]:
            st.markdown(f"**{f}**")
            st.session_state.alloc[f] = st.number_input(
                "%",
                0, 100,
                st.session_state.alloc[f],
                key=f
            )

    total = sum(st.session_state.alloc.values())

    if total != 100:
        st.error(f"Totaal = {total}% (moet 100%)")
        st.stop()

    weights = pd.Series(st.session_state.alloc)/100

    port = (returns[selected] * weights).sum(axis=1)

    st.subheader("Simulatie")

    value = capital * (1 + port).cumprod()
    st.line_chart(value)

    # MONTE CARLO
    st.subheader("Monte Carlo")

    if len(port) > 20:
        sims = np.random.normal(port.mean(), port.std(), (252, 200))
        sims = capital * np.cumprod(1 + sims, axis=0)

        mc = pd.DataFrame({
            "Worst": np.percentile(sims,10,axis=1),
            "Expected": np.percentile(sims,50,axis=1),
            "Best": np.percentile(sims,90,axis=1)
        })

        st.line_chart(mc)