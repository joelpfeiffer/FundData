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
# TOOLTIP HELPER
# =========================
def section(title, tooltip):
    col1, col2 = st.columns([10,1])
    with col1:
        st.subheader(title)
    with col2:
        st.markdown(f"<span title='{tooltip}'>ℹ️</span>", unsafe_allow_html=True)

# =========================
# LOAD
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load()

pivot_full = df.pivot(index="date", columns="fund", values="price")

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

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    section(
        "Prijsontwikkeling (€)",
        "Deze grafiek toont de absolute prijs van elk geselecteerd fonds over tijd.\n\n"
        "Gebruik:\n"
        "- Vergelijk prijsniveau en stabiliteit\n"
        "- Kijk naar trends (stijgend/dalend)\n\n"
        "Let op:\n"
        "Fondsen met hogere prijzen zijn niet per se beter — kijk naar groei, niet alleen niveau."
    )

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(xaxis_title="Date", yaxis_title="Price (€)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    section(
        "Trends (genormaliseerd)",
        "Alle fondsen starten op 100 zodat prestaties eerlijk vergeleken kunnen worden.\n\n"
        "Gebruik:\n"
        "- Zie welk fonds beter presteert\n"
        "- Directe vergelijking mogelijk\n\n"
        "Interpretatie:\n"
        "120 = +20% rendement\n"
        "90 = -10% verlies"
    )

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    fig2.update_layout(xaxis_title="Date", yaxis_title="Index (100 = start)", hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    section(
        "Momentum (%)",
        "Momentum meet het recente rendement over een vaste periode.\n\n"
        "Gebruik:\n"
        "- Identificeer stijgende (sterke) fondsen\n"
        "- Spot dalende trends\n\n"
        "Interpretatie:\n"
        "Positief = stijgende trend\n"
        "Negatief = dalende trend\n\n"
        "Let op:\n"
        "Momentum kan snel veranderen en is geen garantie voor toekomst."
    )

    shift = min(30, len(pivot)-1)
    mom = (pivot/pivot.shift(shift)-1)*100
    last = mom.iloc[-1].dropna()

    if not last.empty:
        fig = go.Figure(go.Bar(x=last.index, y=last.values))
        fig.update_layout(xaxis_title="Fund", yaxis_title="Return (%)")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    section(
        "Volatility",
        "Volatility meet hoe sterk een fonds schommelt.\n\n"
        "Gebruik:\n"
        "- Hoog = meer risico\n"
        "- Laag = stabieler\n\n"
        "Let op:\n"
        "Hoge volatiliteit betekent grotere ups én downs."
    )

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    section(
        "Sharpe Ratio",
        "Sharpe ratio meet rendement per risico.\n\n"
        "Gebruik:\n"
        "- Hoger = efficiënter rendement\n\n"
        "Interpretatie:\n"
        ">1 = goed\n"
        ">2 = sterk\n"
        "<1 = zwakker risico/rendement"
    )

    sharpe = (returns.mean()*TRADING_DAYS) / vol
    st.dataframe(sharpe.to_frame("Sharpe"))

    section(
        "Correlation Matrix",
        "Toont hoe fondsen samen bewegen.\n\n"
        "Interpretatie:\n"
        "1 = bewegen gelijk\n"
        "0 = onafhankelijk\n"
        "-1 = tegenovergesteld\n\n"
        "Gebruik:\n"
        "Lage correlatie = betere spreiding"
    )

    fig = px.imshow(returns.corr(), text_auto=True, color_continuous_scale="RdBu", zmin=-1, zmax=1)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    section(
        "Return Heatmap (%)",
        "Rendement per fonds over verschillende periodes.\n\n"
        "Gebruik:\n"
        "- Snel overzicht van prestaties\n"
        "- Spot korte vs lange termijn trends\n\n"
        "Kleuren:\n"
        "Groen = positief\n"
        "Rood = negatief\n\n"
        "Waarde in cel = percentage rendement"
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

    heatmap = pd.DataFrame({k: calc(v) for k,v in periods.items()}).dropna(how="all")

    if not heatmap.empty:
        fig = go.Figure(data=go.Heatmap(
            z=heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            colorscale="RdYlGn",
            zmid=0,
            text=heatmap.round(2).astype(str)+"%",
            texttemplate="%{text}"
        ))
        fig.update_layout(xaxis_title="Period", yaxis_title="Fund")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    section(
        "Portfolio Optimizer",
        "Toont een voorbeeldverdeling van fondsen.\n\n"
        "Let op:\n"
        "Dit is een random verdeling en geen advies.\n\n"
        "Gebruik:\n"
        "In echte scenario’s gebruik je optimalisatie op basis van risico/rendement."
    )

    w = np.random.random(len(selected))
    w /= w.sum()

    st.dataframe(pd.DataFrame({
        "Fund": selected,
        "Weight": w
    }))

# =========================
# REBALANCE
# =========================
with tab6:
    section(
        "Rebalance Simulator",
        "Simuleert hoe je portfolio groeit op basis van gekozen verdeling.\n\n"
        "Gebruik:\n"
        "- Test verschillende verdelingen\n"
        "- Zie impact op groei\n\n"
        "Let op:\n"
        "Gebaseerd op historische data"
    )

    st.warning(
        "Deze simulatie is uitsluitend bedoeld voor informatieve en educatieve doeleinden. "
        "Er kunnen geen rechten aan worden ontleend. Resultaten uit het verleden bieden geen garantie voor de toekomst."
    )

    capital = st.number_input("Start (€)", 100, 1000000, 10000)

    weights = {}
    cols = st.columns(len(selected))

    for i,f in enumerate(selected):
        weights[f] = cols[i].slider(f,0.0,1.0,1/len(selected))

    w = np.array(list(weights.values()))
    w /= w.sum()

    port = (returns*w).sum(axis=1)

    section(
        "Historische portfolio waarde",
        "Laat zien hoe je portfolio zich zou hebben ontwikkeld in het verleden."
    )

    value = capital*(1+port).cumprod()

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=value.index,y=value))
    fig_hist.update_layout(xaxis_title="Date", yaxis_title="Portfolio (€)")
    st.plotly_chart(fig_hist, use_container_width=True)

    section(
        "Monte Carlo Simulation",
        "Simuleert mogelijke toekomstige scenario’s.\n\n"
        "Lijnen:\n"
        "- Worst case = slecht scenario\n"
        "- Expected = meest waarschijnlijk\n"
        "- Best case = gunstig scenario\n\n"
        "Gebruik:\n"
        "Helpt risico en onzekerheid te begrijpen"
    )

    if len(port) >= 5:
        mean = port.mean()
        std = port.std()

        horizon = 252
        sims = 1000

        simulations = np.random.normal(mean, std, (horizon, sims))
        simulations = capital * np.cumprod(1 + simulations, axis=0)

        worst = np.percentile(simulations, 10, axis=1)
        expected = np.percentile(simulations, 50, axis=1)
        best = np.percentile(simulations, 90, axis=1)

        fig_mc = go.Figure()
        fig_mc.add_trace(go.Scatter(y=worst, name="Worst case"))
        fig_mc.add_trace(go.Scatter(y=expected, name="Expected"))
        fig_mc.add_trace(go.Scatter(y=best, name="Best case"))

        fig_mc.update_layout(xaxis_title="Days", yaxis_title="Portfolio (€)")
        st.plotly_chart(fig_mc, use_container_width=True)
    else:
        st.warning("Te weinig data voor Monte Carlo")