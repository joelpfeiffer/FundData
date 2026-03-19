import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
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
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")

df = load_data()

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

# 👉 onboarding knop ONDERAAN
st.sidebar.markdown("---")
if st.sidebar.button("Start onboarding"):
    st.session_state.onboarding = True

# =========================
# FILTER DATA
# =========================
pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

returns = pivot.pct_change().dropna()

# =========================
# TABS
# =========================
tabs = st.tabs(["Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"])
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = tabs

# =========================
# OVERVIEW (HERSTELD)
# =========================
with tab1:
    st.subheader("Overview")

    if len(pivot) > 1:
        ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100

        col1,col2,col3,col4,col5 = st.columns(5)

        col1.metric("Gem. rendement", f"{ret.mean():.2f}%")
        col2.metric("Beste fonds", ret.idxmax())
        col3.metric("Slechtste fonds", ret.idxmin())

        vol = returns.std().mean() * np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean().mean() * TRADING_DAYS) / vol if vol != 0 else 0

        col4.metric("Volatiliteit", f"{vol:.2f}")
        col5.metric("Sharpe", f"{sharpe:.2f}")

    # 👉 TREND TERUG
    st.markdown("### Prijsontwikkeling")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

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
    sharpe = (returns.mean() * TRADING_DAYS) / vol.replace(0,np.nan)

    st.dataframe(pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe
    }))

    st.plotly_chart(px.imshow(returns.corr(), text_auto=True), use_container_width=True)

# =========================
# HEATMAP (GEFIXT)
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365,"2Y":730,"5Y":1825
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
            [0, "red"],
            [0.5, "yellow"],
            [1, "green"]
        ],
        zmid=0,
        text=np.round(heat.values,2),
        texttemplate="%{text}%",
        hovertemplate="%{y} - %{x}: %{z:.2f}%"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")
    w = np.random.random(len(selected))
    w /= w.sum()
    st.dataframe(pd.DataFrame({"Fund": selected, "Weight %": w*100}))

# =========================
# REBALANCE
# =========================
with tab6:
    st.subheader("Rebalance")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    weights = pd.Series(1/len(selected), index=selected)
    port = (returns[weights.index] * weights).sum(axis=1)

    st.line_chart(capital * (1+port).cumprod())

# =========================
# RAW DATA (EXCEL FIX)
# =========================
with tab7:
    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)]

    view = st.radio("Weergave", ["Long","Wide"], horizontal=True)

    if view == "Wide":
        display = raw.pivot(index="date", columns="fund", values="price")
    else:
        display = raw

    st.dataframe(display)

    col1,col2 = st.columns(2)

    # CSV
    col1.download_button(
        "Download CSV",
        display.to_csv().encode("utf-8"),
        "data.csv"
    )

    # ✅ EXCEL FIX (zonder engine)
    output = BytesIO()
    with pd.ExcelWriter(output) as writer:
        display.to_excel(writer)

    col2.download_button(
        "Download Excel",
        output.getvalue(),
        "data.xlsx"
    )