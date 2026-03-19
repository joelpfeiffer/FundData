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

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

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

    st.subheader(
        "Overview",
        help="Samenvatting van prestaties, risico en beste/slechtste fondsen."
    )

    if not pivot.empty:
        start_date = pivot.index.min().strftime("%d-%m-%Y")
        end_date = pivot.index.max().strftime("%d-%m-%Y")
        days = (pivot.index.max() - pivot.index.min()).days

        st.caption(
            f"Periode: {start_date} → {end_date} ({days} dagen). "
            "Gebaseerd op dagelijkse rendementen."
        )

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

    st.subheader(
        "Prijsontwikkeling",
        help="Toont de absolute prijs per fonds over tijd."
    )

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(
        hovermode="x unified",
        xaxis=dict(title="Datum", showspikes=True),
        yaxis=dict(title="Prijs", showspikes=True)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader(
        "Genormaliseerde groei",
        help="Alle fondsen starten op 100 zodat prestaties eerlijk vergelijkbaar zijn."
    )

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    fig2.update_layout(
        hovermode="x unified",
        xaxis=dict(title="Datum", showspikes=True),
        yaxis=dict(title="Index (start=100)", showspikes=True)
    )

    st.plotly_chart(fig2, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:

    st.subheader(
        "Momentum (30 dagen)",
        help="Percentage verandering over de laatste 30 dagen."
    )

    if len(pivot) < 30:
        st.warning("Te weinig data (<30 dagen)")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        last = mom.iloc[-1].dropna()

        fig = go.Figure(go.Bar(x=last.index, y=last.values))
        fig.update_layout(xaxis_title="Fonds", yaxis_title="Momentum (%)")
        st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:

    st.subheader(
        "Risk metrics",
        help="Volatiliteit = risico. Sharpe = rendement per risico-eenheid."
    )

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0, np.nan)

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe
    })

    st.dataframe(risk_df)

    st.subheader(
        "Correlatie",
        help="Laat zien hoe fondsen samen bewegen (-1 tot +1)."
    )

    fig = px.imshow(
        returns.corr(),
        text_auto=True,
        color_continuous_scale="RdYlGn",
        zmin=-1,
        zmax=1
    )

    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader(
        "Heatmap",
        help="Toont rendement per periode. Groen = positief, rood = negatief."
    )

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"1W":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825
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
    st.subheader("Optimizer", help="Simpele verdeling van gewichten.")
    weights = np.random.random(len(selected))
    weights /= weights.sum()
    st.dataframe(pd.DataFrame({"Fund": selected, "Weight (%)": (weights*100).round(2)}))

# =========================
# REBALANCE
# =========================
with tab6:

    st.subheader("Rebalance", help="Simuleer portfolio groei.")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    weights = pd.Series(1/len(selected), index=selected)
    port = (returns[weights.index]*weights).sum(axis=1)

    st.line_chart(capital*(1+port).cumprod())

    st.subheader(
        "Monte Carlo simulatie",
        help="Simuleert mogelijke toekomstige uitkomsten."
    )

    if len(port) < 50:
        st.warning("Te weinig data (<50 dagen)")
    else:
        mu, sigma = port.mean(), port.std()
        sims = np.random.normal(mu, sigma, (252, 200))
        sims = capital * np.cumprod(1 + sims, axis=0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=np.percentile(sims,10,axis=1), name="Worst"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,50,axis=1), name="Expected"))
        fig.add_trace(go.Scatter(y=np.percentile(sims,90,axis=1), name="Best"))

        st.plotly_chart(fig, use_container_width=True)

# =========================
# RAW DATA
# =========================
with tab7:

    st.subheader("Raw Data", help="Bekijk en download de onderliggende data.")

    raw = df[df["fund"].isin(selected)].copy()

    view = st.radio("Weergave", ["Long", "Wide"], horizontal=True)

    if view == "Long":
        st.dataframe(raw)
    else:
        st.dataframe(raw.pivot(index="date", columns="fund", values="price"))