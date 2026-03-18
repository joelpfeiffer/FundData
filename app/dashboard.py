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
# UI STYLE (POLISH)
# =========================
st.markdown("""
<style>
h1, h2, h3 {
    font-weight: 600;
}
.block-container {
    padding-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

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

st.sidebar.title("Instellingen")

selected = st.sidebar.multiselect(
    "Selecteer fondsen",
    funds,
    default=funds[:5],
    help="Kies welke fondsen je wilt analyseren"
)

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

mode = st.sidebar.radio(
    "Timeframe",
    ["Preset","Custom"],
    help="Preset = snelle selectie, Custom = eigen periode"
)

pivot = pivot_full[selected].copy()

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

    st.subheader("Prijsontwikkeling ℹ️", help="""
    Dit laat de werkelijke prijs van elk fonds zien door de tijd.

    Hoe lees je dit:
    - Elke lijn is een fonds
    - Hogere lijn = hogere prijs
    - Gebruik de verticale lijn (hover) om fondsen op dezelfde datum te vergelijken
    """)

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(
        xaxis_title="Datum",
        yaxis_title="Prijs (€)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Genormaliseerde groei (%) ℹ️", help="""
    Alle fondsen starten hier op dezelfde waarde (100).

    Dit laat zien:
    - Welk fonds het beste presteert
    - Procentuele groei t.o.v. startpunt

    Hoe lees je dit:
    - 120 = +20% groei
    - 90 = -10% daling
    """)

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    fig2.update_layout(
        xaxis_title="Datum",
        yaxis_title="Index (start = 100)",
        hovermode="x unified"
    )

    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader("Momentum (%) ℹ️", help="""
    Momentum laat zien hoeveel een fonds is gestegen of gedaald over de laatste periode.

    Hoe lees je dit:
    - Positief = stijging
    - Negatief = daling
    - Hoe hoger, hoe sterker de trend
    """)

    if len(pivot) > 10:
        shift = min(30, len(pivot)-1)
        mom = (pivot / pivot.shift(shift) - 1) * 100
        last = mom.iloc[-1].dropna()

        if not last.empty:
            df_plot = last.sort_values(ascending=False)

            fig = go.Figure(go.Bar(
                x=df_plot.index,
                y=df_plot.values
            ))

            fig.update_layout(
                xaxis_title="Fund",
                yaxis_title="Return (%)"
            )

            st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Volatility ℹ️", help="""
    Volatility meet hoeveel een fonds schommelt.

    - Hoog = meer risico
    - Laag = stabieler
    """)

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    st.subheader("Sharpe Ratio ℹ️", help="""
    Sharpe Ratio meet rendement vs risico.

    - Hoger = beter rendement per risico
    - Lager = inefficiënt
    """)

    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0, np.nan)
    st.dataframe(sharpe.to_frame("Sharpe"))

    st.subheader("Correlatie ℹ️", help="""
    Laat zien hoe fondsen samen bewegen.

    - 1 = bewegen hetzelfde
    - 0 = onafhankelijk
    - -1 = tegenovergesteld
    """)

    fig = px.imshow(returns.corr(), text_auto=True, color_continuous_scale="RdYlGn", zmin=-1, zmax=1)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader("Rendement Heatmap ℹ️", help="""
    Overzicht van rendement per periode.

    - Groen = winst
    - Rood = verlies
    - Geel = neutraal
    """)

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
    heatmap = heatmap.loc[[f for f in selected if f in heatmap.index]]

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
# REBALANCE + MONTE CARLO
# =========================
with tab6:

    st.subheader("Portfolio verdeling (%) ℹ️", help="""
    Verdeel je kapitaal over fondsen.

    - Totaal moet 100% zijn
    - Hiermee simuleer je je portfolio
    """)

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    if "alloc" not in st.session_state:
        st.session_state.alloc = {}

    st.session_state.alloc = {k:v for k,v in st.session_state.alloc.items() if k in selected}

    for f in selected:
        if f not in st.session_state.alloc:
            st.session_state.alloc[f] = int(100/len(selected))

    cols = st.columns(len(selected))

    for i, f in enumerate(selected):
        with cols[i]:
            st.markdown(f"**{f}**")
            st.session_state.alloc[f] = st.number_input("%",0,100,st.session_state.alloc[f],key=f"alloc_{f}")

    total = sum(st.session_state.alloc.values())

    if total != 100:
        st.error(f"Totaal = {total}% (moet 100%)")
        st.stop()

    weights = pd.Series(st.session_state.alloc)/100
    port = (returns[weights.index]*weights).sum(axis=1)

    st.subheader("Simulatie ℹ️", help="Laat zien hoe je portfolio historisch gegroeid zou zijn")

    st.line_chart(capital*(1+port).cumprod())

    st.subheader("Monte Carlo simulatie ℹ️", help="""
    Simuleert mogelijke toekomstige scenario's.

    - Expected = meest waarschijnlijke
    - Worst = slecht scenario
    - Best = optimistisch scenario
    """)

    if len(port) > 30:
        mu, sigma = port.mean(), port.std()

        sims = np.random.normal(mu, sigma, (252, 300))
        sims = capital * np.cumprod(1 + sims, axis=0)

        mc = pd.DataFrame({
            "Worst": np.percentile(sims, 10, axis=1),
            "Expected": np.percentile(sims, 50, axis=1),
            "Best": np.percentile(sims, 90, axis=1)
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=mc["Worst"], name="Worst", line=dict(color="red")))
        fig.add_trace(go.Scatter(y=mc["Expected"], name="Expected", line=dict(color="yellow")))
        fig.add_trace(go.Scatter(y=mc["Best"], name="Best", line=dict(color="green")))

        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)