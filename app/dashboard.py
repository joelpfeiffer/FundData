import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide", page_title="Funds Dashboard")

# =========================
# TOOLTIP POPUP
# =========================
def section(title, tooltip):
    col1, col2 = st.columns([20,1])

    with col1:
        st.subheader(title)

    with col2:
        if st.button("ℹ️", key=title):
            st.session_state[f"show_{title}"] = True

    if st.session_state.get(f"show_{title}", False):
        st.info(tooltip)
        if st.button("Sluiten", key=f"close_{title}"):
            st.session_state[f"show_{title}"] = False

# =========================
# ONBOARDING
# =========================
if "onboarding" not in st.session_state:
    st.session_state.onboarding = True

# =========================
# DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("Timeframe")

mode = st.sidebar.radio("Mode", ["Preset", "Custom"])

pivot = pivot_full[selected]

if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","3Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365,"3Y":1095}

    if tf != "ALL":
        pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
else:
    start = st.sidebar.date_input("Start date", pivot.index.min())
    end = st.sidebar.date_input("End date", pivot.index.max())
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

returns = pivot.pct_change().dropna()

# onboarding reset
st.sidebar.markdown("---")
if st.sidebar.button("Start onboarding opnieuw"):
    st.session_state.onboarding = True

# =========================
# ONBOARDING FLOW
# =========================
if st.session_state.onboarding:
    st.info("""
Welkom bij het dashboard

Stap 1: Selecteer fondsen links  
Stap 2: Kies timeframe  
Stap 3: Gebruik tabs  

Overview → trends  
Performance → rendement  
Risk → risico  
Heatmap → overzicht  
Rebalance → simulaties
""")

    if st.button("Start"):
        st.session_state.onboarding = False
        st.rerun()

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
    section("Prijsontwikkeling (€)", """
Wat zie je:
De prijs van elk fonds over tijd.

Hoe lees je dit:
Elke lijn = een fonds
Stijging = waarde neemt toe

Waar op letten:
Prijs ≠ performance
Kijk naar trend, niet alleen niveau
""")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(xaxis_title="Datum", yaxis_title="Prijs (€)")
    st.plotly_chart(fig, use_container_width=True)

    section("Genormaliseerde groei", """
Wat zie je:
Alle fondsen starten op 100.

Hoe lees je dit:
120 = +20%
80 = -20%

Waar op letten:
Beste vergelijking tussen fondsen
""")

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section("Momentum (%)", """
Wat zie je:
Recente performance.

Hoe lees je:
Positief = stijging
Negatief = daling

Waar op letten:
Korte termijn indicator
""")

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        df_plot = last.sort_values(ascending=False)

        fig = go.Figure(go.Bar(
            x=df_plot.index,
            y=df_plot.values
        ))

        fig.update_layout(xaxis_title="Fund", yaxis_title="Return (%)")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    section("Volatility", """
Wat zie je:
Schommelingen (risico).

Hoe lees je:
Hoger = risicovoller

Waar op letten:
Meer risico ≠ slecht
""")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    section("Sharpe Ratio", """
Wat zie je:
Rendement vs risico.

Hoe lees je:
Hoger = beter

Waar op letten:
Belangrijkste metric
""")

    sharpe = (returns.mean()*TRADING_DAYS) / vol
    st.dataframe(sharpe.to_frame("Sharpe"))

    section("Correlatie", """
Wat zie je:
Samenhang tussen fondsen.

Hoe lees je:
1 = hetzelfde
0 = onafhankelijk

Waar op letten:
Lage correlatie = goede spreiding
""")

    fig = px.imshow(returns.corr(), text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    section("Rendement Heatmap", """
Wat zie je:
Rendement over verschillende periodes.

Hoe lees je:
Groen = winst
Rood = verlies

Waar op letten:
Horizontaal = tijd
Verticaal = fonds
""")

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,"6M":180,
        "1Y":365,"2Y":730,"5Y":1825
    }

    def calc(days):
        past = df_full[df_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=df_full.columns)
        return (df_full.loc[latest]/past.iloc[-1]-1)*100

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()})

    fig = go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns,
        y=heatmap.index,
        colorscale="RdYlGn",
        text=heatmap.round(2).astype(str)+"%",
        texttemplate="%{text}"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    section("Portfolio verdeling", """
Wat zie je:
Verdeling van investeringen.

Hoe lees je:
Weight = percentage

Waar op letten:
Spreiding verlaagt risico
""")

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({"Fund": selected, "Weight": w}))

# =========================
# REBALANCE
# =========================
with tab6:
    section("Simulatie", """
Wat zie je:
Groei van je portfolio.

Hoe lees je:
Lijn = waarde

Waar op letten:
Gebaseerd op historische data
""")

    st.warning("Dit is geen financieel advies")

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)

    value = capital*(1+port).cumprod()
    st.line_chart(value)

    section("Monte Carlo", """
Wat zie je:
Toekomstscenario’s.

Hoe lees je:
Expected = gemiddelde
Worst = slecht
Best = goed

Waar op letten:
Geen voorspelling
""")

    if len(port) > 10:
        sims = np.random.normal(port.mean(), port.std(), (252,500))
        sims = capital*np.cumprod(1+sims,axis=0)

        st.line_chart(pd.DataFrame({
            "Worst": np.percentile(sims,10,axis=1),
            "Expected": np.percentile(sims,50,axis=1),
            "Best": np.percentile(sims,90,axis=1)
        }))