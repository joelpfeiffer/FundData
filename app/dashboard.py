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

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

pivot = pivot_full[selected].copy()

if mode == "Preset":
    tf = st.sidebar.selectbox("Range", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}

    if tf != "ALL" and len(pivot) > 0:
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

    st.subheader("Prijsontwikkeling")
    st.caption("Werkelijke prijzen van fondsen door de tijd.")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Genormaliseerde groei (%)")
    st.caption("Vergelijkt prestaties vanaf hetzelfde startpunt (100).")

    if len(pivot) > 0:
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

    st.subheader("Momentum (%)")
    st.caption("Recente stijging of daling van fondsen.")

    if len(pivot) > 10:
        shift = min(30, len(pivot)-1)
        mom = (pivot / pivot.shift(shift) - 1) * 100
        last = mom.iloc[-1].dropna()

        if not last.empty:
            df_plot = last.sort_values(ascending=False)

            fig = go.Figure(go.Bar(
                x=df_plot.index.astype(str),
                y=df_plot.values
            ))

            st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:

    st.subheader("Volatility")
    st.caption("Mate van schommelingen (risico).")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    st.dataframe(vol.to_frame("Volatility"))

    st.subheader("Sharpe Ratio")
    st.caption("Rendement per eenheid risico.")

    sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0, np.nan)
    st.dataframe(sharpe.to_frame("Sharpe"))

    st.subheader("Correlatie")
    st.caption("Hoe fondsen samen bewegen.")

    fig = px.imshow(
        returns.corr(),
        text_auto=True,
        color_continuous_scale="RdYlGn",
        zmin=-1,
        zmax=1
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:

    st.subheader("Rendement Heatmap")
    st.caption("Groen = winst, Rood = verlies.")

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
# OPTIMIZER
# =========================
with tab5:

    st.subheader("Portfolio verdeling (voorbeeld)")
    st.caption("Simpele verdeling ter illustratie.")

    w = np.random.random(len(selected))
    w /= w.sum()

    df_opt = pd.DataFrame({
        "Fund": selected,
        "Weight (%)": (w*100).round(2)
    })

    st.dataframe(df_opt)

# =========================
# REBALANCE
# =========================
with tab6:

    st.subheader("Portfolio verdeling (%)")
    st.caption("Verdeel je kapitaal over fondsen (totaal = 100%).")

    capital = st.number_input("Startkapitaal (€)", 100, 1000000, 10000)

    if "alloc" not in st.session_state:
        st.session_state.alloc = {}

    st.session_state.alloc = {
        k: v for k, v in st.session_state.alloc.items() if k in selected
    }

    for f in selected:
        if f not in st.session_state.alloc:
            st.session_state.alloc[f] = int(100/len(selected))

    cols = st.columns(len(selected))

    for i, f in enumerate(selected):
        with cols[i]:
            st.markdown(f"**{f}**")
            st.session_state.alloc[f] = st.number_input(
                "%",
                0, 100,
                st.session_state.alloc[f],
                key=f"alloc_{f}"
            )

    total = sum(st.session_state.alloc.values())

    if total != 100:
        st.error(f"Totaal = {total}% (moet 100%)")
        st.stop()

    weights = pd.Series(st.session_state.alloc)/100
    port = (returns[weights.index]*weights).sum(axis=1)

    st.subheader("Simulatie")
    st.line_chart(capital*(1+port).cumprod())

    st.subheader("Monte Carlo simulatie")

    if len(port) > 30:
        mu, sigma = port.mean(), port.std()

        if not np.isnan(mu) and not np.isnan(sigma) and sigma > 0:
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