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
# TOOLTIP
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
# LOAD DATA
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
# (ALLE ANDERE TABS BLIJVEN EXACT HETZELFDE)
# =========================

with tab6:

    section("Portfolio verdeling (%)", """
Stel je portefeuille samen.

Hoe lees je:
- Percentage = deel van je investering
- Totaal moet 100% zijn
""")

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    st.markdown("### Verdeling (%)")

    perc = {}
    cols = st.columns(len(selected))

    for i, fund in enumerate(selected):
        perc[fund] = cols[i].slider(
            fund,
            min_value=0,
            max_value=100,
            value=int(100/len(selected))
        )

    total = sum(perc.values())

    # =========================
    # CHECK 100%
    # =========================
    if total != 100:
        st.error(f"Totaal is {total}%. Dit moet exact 100% zijn.")
        st.stop()
    else:
        st.success("Verdeling klopt (100%)")

    # =========================
    # OMZETTEN NAAR WEIGHTS
    # =========================
    w = np.array(list(perc.values())) / 100

    # =========================
    # PORTFOLIO RETURNS
    # =========================
    port = (returns[selected] * w).sum(axis=1)

    # =========================
    # HISTORIE
    # =========================
    section("Historische simulatie", """
Toont hoe je portfolio zich had ontwikkeld.
""")

    value = capital * (1 + port).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=value.index, y=value.values))
    fig.update_layout(xaxis_title="Datum", yaxis_title="Waarde (€)")

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # MONTE CARLO
    # =========================
    section("Monte Carlo", """
Simulatie van mogelijke toekomstscenario’s.
""")

    if len(port) > 10:
        sims = np.random.normal(port.mean(), port.std(), (252,500))
        sims = capital * np.cumprod(1 + sims, axis=0)

        mc = pd.DataFrame({
            "Worst": np.percentile(sims,10,axis=1),
            "Expected": np.percentile(sims,50,axis=1),
            "Best": np.percentile(sims,90,axis=1)
        })

        st.line_chart(mc)

    st.warning("Dit is geen financieel advies")