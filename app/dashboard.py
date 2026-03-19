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
# ONBOARDING STATE
# =========================
if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = -1

def show_onboarding():
    if st.session_state.onboarding_step == -1:
        return

    steps = [
        ("Welkom", "Welkom! Dit dashboard helpt je fondsen analyseren."),
        ("Sidebar", "Selecteer fondsen en timeframe links."),
        ("Overview", "Bekijk hier prestaties en trends."),
        ("Performance", "Momentum laat recente beweging zien."),
        ("Risk", "Volatiliteit = risico, Sharpe = efficiëntie."),
        ("Heatmap", "Vergelijk rendement over tijd."),
        ("Rebalance", "Simuleer portfolio groei."),
        ("Klaar", "Succes met analyseren!")
    ]

    step = st.session_state.onboarding_step
    title, text = steps[step]

    st.info(f"**{title}**\n\n{text}")

    col1, col2 = st.columns(2)

    if step > 0:
        if col1.button("⬅ Vorige"):
            st.session_state.onboarding_step -= 1

    if step < len(steps) - 1:
        if col2.button("Volgende ➡"):
            st.session_state.onboarding_step += 1
    else:
        if col2.button("Afronden"):
            st.session_state.onboarding_step = -1

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
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

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
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")
returns = pivot.pct_change().dropna()

# =========================
# ONBOARDING DISPLAY
# =========================
show_onboarding()

# =========================
# HELPERS
# =========================
def shorten(name, length=18):
    return name if len(name) <= length else name[:length] + "..."

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

    st.subheader("Overview", help="Samenvatting van prestaties en risico")

    start_date = pivot.index.min().strftime("%d-%m-%Y")
    end_date = pivot.index.max().strftime("%d-%m-%Y")

    st.caption(f"Periode: {start_date} → {end_date}")

    if len(pivot) > 1:
        total_return = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100

        best = total_return.idxmax()
        worst = total_return.idxmin()

        vol = returns.std().mean() * np.sqrt(TRADING_DAYS)
        sharpe = (returns.mean().mean() * TRADING_DAYS) / vol if vol != 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Gem. rendement", f"{total_return.mean():.2f}%")

        col2.metric("Beste fonds", shorten(best))
        col2.caption(best)

        col3.metric("Slechtste fonds", shorten(worst))
        col3.caption(worst)

        col4.metric("Volatiliteit", f"{vol:.2f}")
        col5.metric("Sharpe", f"{sharpe:.2f}")

    st.markdown("---")

    st.subheader("Prijsontwikkeling", help="Absolute prijs")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Genormaliseerde groei", help="Start = 100")

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    fig2.update_layout(hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader("Momentum (30 dagen)", help="Trend indicator")

    if len(pivot) >= 30:
        mom = (pivot / pivot.shift(30) - 1) * 100
        st.bar_chart(mom.iloc[-1].dropna())
    else:
        st.warning("Te weinig data")

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Risk metrics", help="Volatiliteit en Sharpe")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0, np.nan)

    st.dataframe(pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe
    }))

    st.subheader("Correlatie")

    st.plotly_chart(px.imshow(returns.corr(), text_auto=True))

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {"1D":1,"1W":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825}

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()})
    heatmap = heatmap.loc[selected]

    st.plotly_chart(go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns,
        y=heatmap.index,
        colorscale="RdYlGn",
        zmid=0
    )))

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")
    weights = np.random.random(len(selected))
    weights /= weights.sum()
    st.dataframe(pd.DataFrame({"Fund": selected, "Weight %": weights*100}))

# =========================
# REBALANCE
# =========================
with tab6:

    st.subheader("Rebalance")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    weights = pd.Series(1/len(selected), index=selected)
    port = (returns[weights.index]*weights).sum(axis=1)

    st.line_chart(capital*(1+port).cumprod())

    st.subheader("Monte Carlo")

    if len(port) >= 50:
        mu, sigma = port.mean(), port.std()
        sims = np.random.normal(mu, sigma, (252, 200))
        sims = capital * np.cumprod(1 + sims, axis=0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=np.percentile(sims,10,axis=1), name="Worst"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,50,axis=1), name="Expected"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,90,axis=1), name="Best"))

        st.plotly_chart(fig)
    else:
        st.warning("Te weinig data")

# =========================
# RAW DATA
# =========================
with tab7:

    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)]

    st.dataframe(raw)