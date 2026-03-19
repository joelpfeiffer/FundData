import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time
from io import BytesIO

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide")

# =========================
# ONBOARDING
# =========================
if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = -1

def show_onboarding():
    if st.session_state.onboarding_step == -1:
        return

    steps = [
        ("Welkom", "Welkom! Analyseer fondsen en trends."),
        ("Sidebar", "Selecteer fondsen en timeframe."),
        ("Overview", "Bekijk prestaties."),
        ("Performance", "Momentum = trend."),
        ("Risk", "Risico en Sharpe."),
        ("Heatmap", "Vergelijk rendement."),
        ("Rebalance", "Simuleer portfolio."),
        ("Klaar", "Succes!")
    ]

    step = st.session_state.onboarding_step
    title, text = steps[step]

    st.info(f"**{title}**\n\n{text}")

    c1, c2 = st.columns(2)

    if step > 0 and c1.button("⬅ Vorige"):
        st.session_state.onboarding_step -= 1

    if step < len(steps)-1 and c2.button("Volgende ➡"):
        st.session_state.onboarding_step += 1

    if step == len(steps)-1 and c2.button("Afronden"):
        st.session_state.onboarding_step = -1

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
mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

if st.sidebar.button("Start onboarding"):
    st.session_state.onboarding_step = 0

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected].copy()

# =========================
# TIMEFRAME
# =========================
if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
else:
    start = st.sidebar.date_input("Start", pivot.index.min())
    end = st.sidebar.date_input("End", pivot.index.max())
    pivot = pivot[(pivot.index>=pd.to_datetime(start)) & (pivot.index<=pd.to_datetime(end))]

pivot = pivot.dropna(how="all")
returns = pivot.pct_change().dropna()

# onboarding tonen
show_onboarding()

# =========================
# HELPERS
# =========================
def shorten(x, n=18):
    return x if len(x)<=n else x[:n]+"..."

# =========================
# TABS
# =========================
tabs = st.tabs(["Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"])
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = tabs

# =========================
# OVERVIEW
# =========================
with tab1:

    st.subheader("Overview", help="Samenvatting")

    st.caption(f"{pivot.index.min().date()} → {pivot.index.max().date()}")

    if len(pivot)>1:
        ret = (pivot.iloc[-1]/pivot.iloc[0]-1)*100
        best = ret.idxmax()
        worst = ret.idxmin()

        vol = returns.std().mean()*np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean().mean()*TRADING_DAYS)/vol if vol!=0 else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Return", f"{ret.mean():.2f}%")
        c2.metric("Beste", shorten(best)); c2.caption(best)
        c3.metric("Slechtste", shorten(worst)); c3.caption(worst)
        c4.metric("Vol", f"{vol:.2f}")
        c5.metric("Sharpe", f"{sharpe:.2f}")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader("Momentum")

    if len(pivot)>=30:
        mom = (pivot/pivot.shift(30)-1)*100
        st.bar_chart(mom.iloc[-1].dropna())
    else:
        st.warning("Te weinig data")

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Risk")

    vol = returns.std()*np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

    st.dataframe(pd.DataFrame({
        "Volatility":vol,
        "Sharpe":sharpe
    }))

    st.plotly_chart(px.imshow(returns.corr(),text_auto=True))

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader("Heatmap")

    latest = pivot_full.index.max()
    periods = {"1D":1,"1W":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825}

    def calc(d):
        past = pivot_full[pivot_full.index<=latest-pd.Timedelta(days=d)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest]/past.iloc[-1]-1)*100

    heat = pd.DataFrame({k:calc(v) for k,v in periods.items()}).loc[selected]

    st.plotly_chart(go.Figure(data=go.Heatmap(
        z=heat.values,
        x=heat.columns,
        y=heat.index,
        colorscale="RdYlGn",
        zmid=0
    )))

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")
    w = np.random.random(len(selected))
    w/=w.sum()
    st.dataframe(pd.DataFrame({"Fund":selected,"Weight %":w*100}))

# =========================
# REBALANCE
# =========================
with tab6:

    st.subheader("Rebalance")

    capital = st.number_input("Kapitaal",100,1000000,10000)

    weights = pd.Series(1/len(selected),index=selected)
    port = (returns[weights.index]*weights).sum(axis=1)

    st.line_chart(capital*(1+port).cumprod())

    st.subheader("Monte Carlo")

    if len(port)>=50:
        mu,sigma = port.mean(),port.std()
        sims = np.random.normal(mu,sigma,(252,200))
        sims = capital*np.cumprod(1+sims,axis=0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=np.percentile(sims,10,axis=1),name="Worst"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,50,axis=1),name="Expected"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,90,axis=1),name="Best"))
        st.plotly_chart(fig)
    else:
        st.warning("Te weinig data")

# =========================
# RAW DATA (FIXED)
# =========================
with tab7:

    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)].copy()

    view = st.radio("Weergave",["Long","Wide"],horizontal=True)

    if view=="Long":
        display = raw.sort_values(["date","fund"])
    else:
        display = raw.pivot(index="date",columns="fund",values="price")

    st.dataframe(display,use_container_width=True)

    st.markdown("---")
    c1,c2 = st.columns(2)

    # CSV
    c1.download_button(
        "Download CSV",
        display.to_csv().encode("utf-8"),
        "fund_data.csv"
    )

    # Excel (FIXED)
    try:
        output = BytesIO()
        with pd.ExcelWriter(output) as writer:
            display.to_excel(writer, sheet_name="Data")

        c2.download_button(
            "Download Excel",
            output.getvalue(),
            "fund_data.xlsx"
        )
    except:
        st.warning("Excel download niet beschikbaar")