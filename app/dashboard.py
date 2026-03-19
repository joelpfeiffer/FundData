import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "price", "fund"])
    return df.sort_values("date")

df = load_data()

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

if mode == "Preset":
    tf = st.sidebar.selectbox("Periode", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}
else:
    start = st.sidebar.date_input("Start", pivot_full.index.min())
    end = st.sidebar.date_input("End", pivot_full.index.max())

st.sidebar.markdown("---")
st.sidebar.button("Start onboarding")

# =========================
# FILTER DATA
# =========================
if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if pivot.empty:
    st.warning("Geen data in deze periode")
    st.stop()

returns = pivot.pct_change().dropna()

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    st.subheader("Overview")

    start_date = pivot.index.min().strftime("%d-%m-%Y")
    end_date = pivot.index.max().strftime("%d-%m-%Y")
    days = (pivot.index.max() - pivot.index.min()).days

    st.caption(
        f"Periode: {start_date} → {end_date} ({days} dagen). "
        "Rendement = groei | Volatiliteit = risico | Sharpe = rendement per risico."
    )

    if len(pivot) > 1:
        ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100

        best = ret.idxmax()
        worst = ret.idxmin()

        vol = returns.std() * np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

        def short(x):
            return x if len(x) < 18 else x[:18] + "..."

        c1,c2,c3,c4,c5 = st.columns(5)

        c1.metric("Gem. rendement", f"{ret.mean():.2f}%")

        c2.metric("Beste fonds", short(best))
        c2.caption(best)

        c3.metric("Slechtste fonds", short(worst))
        c3.caption(worst)

        c4.metric("Volatiliteit", f"{vol.mean():.2f}")
        c5.metric("Sharpe", f"{sharpe.mean():.2f}")

    st.markdown("---")

    # TREND 1
    st.subheader("Prijsontwikkeling")

    fig = go.Figure()
    benchmark = pivot.mean(axis=1)

    for col in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            name=col,
            line=dict(width=2)
        ))

    fig.add_trace(go.Scatter(
        x=pivot.index,
        y=benchmark,
        name="Benchmark",
        line=dict(dash="dash", width=3)
    ))

    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # TREND 2
    st.subheader("Genormaliseerde groei")

    norm = pivot / pivot.iloc[0] * 100
    bench_norm = norm.mean(axis=1)

    fig2 = go.Figure()

    for col in norm.columns:
        fig2.add_trace(go.Scatter(
            x=norm.index,
            y=norm[col],
            name=col
        ))

    fig2.add_trace(go.Scatter(
        x=norm.index,
        y=bench_norm,
        name="Benchmark",
        line=dict(dash="dash")
    ))

    fig2.update_layout(hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    # DRAWDOWN
    st.subheader("Drawdown")

    drawdown = pivot / pivot.cummax() - 1

    fig3 = go.Figure()

    for col in drawdown.columns:
        fig3.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown[col]*100,
            name=col
        ))

    fig3.update_layout(hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) >= 30:
        mom = (pivot / pivot.shift(30) - 1) * 100
        st.bar_chart(mom.iloc[-1].dropna())
    else:
        st.warning("Te weinig data")

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Risk")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

    # Max drawdown
    drawdown = pivot / pivot.cummax() - 1
    max_dd = drawdown.min()

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe,
        "Max Drawdown %": max_dd * 100
    })

    st.dataframe(risk_df, use_container_width=True)

    # Rolling volatility
    st.subheader("Rolling Volatility (30d)")

    rolling_vol = returns.rolling(30).std() * np.sqrt(TRADING_DAYS)

    fig = go.Figure()
    for col in rolling_vol.columns:
        fig.add_trace(go.Scatter(
            x=rolling_vol.index,
            y=rolling_vol[col],
            name=col
        ))

    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Correlation (groter)
    st.subheader("Correlation Matrix")

    fig_corr = px.imshow(
        returns.corr(),
        text_auto=True,
        aspect="auto"
    )

    fig_corr.update_layout(height=700)
    st.plotly_chart(fig_corr, use_container_width=True)

    # Ranking
    st.subheader("Risk Ranking")

    ranking = risk_df.sort_values("Sharpe", ascending=False)
    st.dataframe(ranking, use_container_width=True)
# =========================
# HEATMAP (ZACHT GEEL)
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,"6M":180,
        "1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest] / past.iloc[-1] - 1) * 100

    heat = pd.DataFrame({k:calc(v) for k,v in periods.items()})
    heat = heat.loc[selected]

    fig = go.Figure(data=go.Heatmap(
        z=heat.values,
        x=heat.columns,
        y=heat.index,
        colorscale=[
            [0, "#d73027"],
            [0.5, "#f5e6a3"],
            [1, "#1a9850"]
        ],
        zmid=0,
        text=np.round(heat.values,2),
        texttemplate="%{text}%"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({
        "Fund": selected,
        "Weight %": w*100
    }))

# =========================
# REBALANCE
# =========================
with tab6:
    st.subheader("Rebalance")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    weights = pd.Series(1/len(selected), index=selected)

    if not returns.empty:
        port = (returns[weights.index] * weights).sum(axis=1)
        st.line_chart(capital * (1+port).cumprod())

# =========================
# RAW DATA
# =========================
with tab7:
    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)]

    view = st.radio("Weergave", ["Long","Wide"], horizontal=True)

    if view == "Wide":
        display = raw.pivot(index="date", columns="fund", values="price")
    else:
        display = raw

    st.dataframe(display, use_container_width=True)

    st.download_button(
        "Download CSV",
        display.to_csv().encode("utf-8"),
        "fund_data.csv"
    )