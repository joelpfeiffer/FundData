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
# TOOLTIP (CLICKBAAR)
# =========================
def section(title, tooltip):
    col1, col2 = st.columns([20,1])
    with col1:
        st.subheader(title)
    with col2:
        with st.expander("ℹ️"):
            st.markdown(tooltip)

# =========================
# ONBOARDING STATE
# =========================
if "onboarding" not in st.session_state:
    st.session_state.onboarding = True

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
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

st.sidebar.markdown("---")

# 🔁 onboarding reset knop
if st.sidebar.button("🔄 Start onboarding opnieuw"):
    st.session_state.onboarding = True

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

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

# =========================
# ONBOARDING UI
# =========================
if st.session_state.onboarding:
    st.info("""
    👋 **Welkom bij het Funds Dashboard**

    Dit dashboard helpt je om fondsen te analyseren.

    🔹 **Stap 1:** Selecteer fondsen in de sidebar  
    🔹 **Stap 2:** Kies een timeframe  
    🔹 **Stap 3:** Gebruik de tabs voor analyse  

    📊 Overzicht → prijs & trends  
    📈 Performance → rendement  
    ⚠️ Risk → risico & correlatie  
    🔥 Heatmap → snelle vergelijking  
    ⚙️ Rebalance → simulaties  

    Klik hieronder om te starten 👇
    """)

    if st.button("Start dashboard"):
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
    section(
        "Prijsontwikkeling (€)",
        """
Dit laat de werkelijke prijs van elk fonds zien.

**Hoe lees je dit:**
- Lijn omhoog = stijgende waarde
- Lijn omlaag = daling

**Gebruik:**
- Bekijk stabiliteit
- Zie lange termijn trend

**Let op:**
Hogere prijs ≠ beter fonds
"""
    )

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(xaxis_title="Datum", yaxis_title="Prijs (€)")
    st.plotly_chart(fig, use_container_width=True)

    section(
        "Trends (genormaliseerd)",
        """
Alle fondsen starten op 100.

**Waarom:**
Zo kun je prestaties eerlijk vergelijken

**Voorbeeld:**
- 120 = +20%
- 80 = -20%
"""
    )

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    fig2.update_layout(xaxis_title="Datum", yaxis_title="Index (100 = start)")
    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section(
        "Momentum (%)",
        """
Laat recente prestaties zien.

**Gebruik:**
- Hoog = sterke trend
- Laag = zwakke trend

**Let op:**
Momentum kan snel draaien
"""
    )

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        st.bar_chart(last)

# =========================
# RISK
# =========================
with tab3:
    section(
        "Volatility",
        """
Meet hoe sterk een fonds beweegt.

**Interpretatie:**
- Hoog = meer risico
- Laag = stabiel
"""
    )

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    section(
        "Sharpe Ratio",
        """
Rendement vs risico.

**Interpretatie:**
- >1 goed
- >2 sterk
"""
    )

    sharpe = (returns.mean()*TRADING_DAYS) / vol
    st.dataframe(sharpe.to_frame("Sharpe"))

    section(
        "Correlation",
        """
Hoe fondsen samen bewegen.

- 1 = gelijk
- 0 = onafhankelijk
- -1 = tegenovergesteld
"""
    )

    fig = px.imshow(returns.corr(), text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    section(
        "Return Heatmap (%)",
        """
Snel overzicht van rendement.

**Kleuren:**
- Groen = winst
- Rood = verlies
"""
    )

    df_full = pivot_full[selected]
    latest = df_full.index.max()

    periods = {
        "1D":1,"2D":2,"1W":7,"2W":14,
        "1M":30,"3M":90,"6M":180,
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
    section(
        "Optimizer",
        """
Voorbeeld verdeling.

**Let op:**
Dit is geen advies
"""
    )

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({"Fund": selected, "Weight": w}))

# =========================
# REBALANCE
# =========================
with tab6:
    section(
        "Rebalance Simulator",
        """
Simuleert portfolio groei.

**Gebruik:**
Test verschillende verdelingen
"""
    )

    st.warning(
        "Deze simulatie is uitsluitend informatief. Geen advies."
    )

    capital = st.number_input("Start (€)", 100, 1000000, 10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)

    value = capital*(1+port).cumprod()
    st.line_chart(value)

    section(
        "Monte Carlo",
        "Simulatie van mogelijke toekomstscenario’s"
    )

    if len(port) >= 5:
        sims = np.random.normal(port.mean(), port.std(), (252,1000))
        sims = capital*np.cumprod(1+sims,axis=0)

        st.line_chart(pd.DataFrame({
            "Worst": np.percentile(sims,10,axis=1),
            "Expected": np.percentile(sims,50,axis=1),
            "Best": np.percentile(sims,90,axis=1)
        }))