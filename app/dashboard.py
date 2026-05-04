import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")
pivot_full = pivot_full.sort_index()

if not pivot_full.empty:
    pivot_full = pivot_full.ffill()

# =========================
# SIDEBAR
# =========================
st.sidebar.title("Instellingen")

funds = list(pivot_full.columns)
selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

mode = st.sidebar.radio("Timeframe", ["Preset","Custom"])

if mode == "Preset":
    tf = st.sidebar.selectbox("Periode", ["1W","2W","1M","3M","6M","1Y","ALL"])
    days_map = {"1W":7,"2W":14,"1M":30,"3M":90,"6M":180,"1Y":365}
else:
    start = st.sidebar.date_input("Start", pivot_full.index.min())
    end = st.sidebar.date_input("End", pivot_full.index.max())

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

# =========================
# FILTER DATA
# =========================
pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    cutoff = pivot.index.max() - pd.Timedelta(days=days_map[tf])
    pivot = pivot.loc[pivot.index >= cutoff]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if len(pivot) < 2:
    st.warning("Te weinig data na filtering")
    st.dataframe(pivot)
    st.stop()

returns = pivot.pct_change().dropna()

if returns.empty:
    st.warning("Te weinig data voor berekeningen")
    st.stop()

# =========================
# CALCULATIONS
# =========================
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

drawdown = pivot / pivot.cummax() - 1
max_dd = drawdown.min()

# =========================
# TABS
# =========================
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

# =========================
# OVERVIEW
# =========================
with tab1:
    st.subheader("Overview")

    best = ret.idxmax()
    worst = ret.idxmin()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
    c2.metric("Beste fonds", best)
    c3.metric("Slechtste fonds", worst)
    c4.metric("Volatiliteit", f"{vol.mean():.2f}")
    c5.metric("Sharpe", f"{sharpe.mean():.2f}")

    if vol.notna().any():
        risico_txt = f"{vol.idxmax()} (volatiliteit {vol.max():.2f})"
    else:
        risico_txt = "Geen volatiliteitsdata"

    st.info(f"""
Beste: {best} (+{ret.max():.2f}%)
Slechtste: {worst} ({ret.min():.2f}%)
Hoogste risico: {risico_txt}
""")

    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    st.plotly_chart(fig,use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) < 30:
        st.warning("Minimaal 30 dagen data nodig")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        mom_last = mom.iloc[-1].dropna().to_frame(name="Momentum")
        mom_last["Fund"] = mom_last.index
        st.bar_chart(mom_last.set_index("Fund"))

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Risk")

    # =========================
    # BASIS METRICS
    # =========================
    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe,
        "Max Drawdown %": max_dd * 100
    })

    st.dataframe(risk_df, use_container_width=True)

    # =========================
    # ROLLING VOLATILITY
    # =========================
    st.subheader("Rolling Volatility (30 dagen)")

    if len(returns) < 30:
        st.warning("Minimaal 30 datapunten nodig")
    else:
        rolling_vol = returns.rolling(30).std() * np.sqrt(TRADING_DAYS)

        rolling_vol = rolling_vol.dropna(how="all")

        if rolling_vol.empty:
            st.warning("Geen rolling volatility data")
        else:
            fig = go.Figure()

            for col in rolling_vol.columns:
                fig.add_trace(go.Scatter(
                    x=rolling_vol.index,
                    y=rolling_vol[col],
                    name=col
                ))

            fig.update_layout(
                xaxis_title="Datum",
                yaxis_title="Volatiliteit"
            )

            st.plotly_chart(fig, use_container_width=True)

    # =========================
    # CORRELATIE
    # =========================
    st.subheader("Correlation Matrix")

    corr = returns.corr()

    if corr.isna().all().all():
        st.warning("Geen correlatie data beschikbaar")
    else:
        fig_corr = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            zmid=0,
            colorscale="RdYlGn"
        ))

        fig_corr.update_layout(height=600)

        st.plotly_chart(fig_corr, use_container_width=True)
# =========================
# HEATMAP (FIXED)
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"1W":7,"1M":30,"3M":90,
        "6M":180,"1Y":365
    }

    def calc(days):
        cutoff = latest - pd.Timedelta(days=days)
        past = pivot_full[pivot_full.index <= cutoff]

        if past.empty:
            return pd.Series(index=pivot_full.columns)

        return (pivot_full.loc[latest] / past.iloc[-1] - 1) * 100

    heat = pd.DataFrame({k:calc(v) for k,v in periods.items()})
    heat = heat.reindex(selected).dropna(how="all")

    if heat.empty:
        st.warning("Geen heatmap data")
    else:
        fig = go.Figure(data=go.Heatmap(
            z=heat.values,
            x=heat.columns,
            y=heat.index,
            zmid=0
        ))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")

    if returns.shape[1] < 2:
        st.warning("Minimaal 2 fondsen nodig")
    else:
        mean_returns = returns.mean()*TRADING_DAYS
        cov_matrix = returns.cov()*TRADING_DAYS

        weights = np.random.random(len(mean_returns))
        weights /= np.sum(weights)

        st.write(dict(zip(mean_returns.index, weights)))

# =========================
# MONTE CARLO
# =========================
with tab6:
    st.subheader("Monte Carlo")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    mean = returns.mean().mean()
    std = returns.std().mean()

    sims = 100
    days = 100

    paths = []

    for _ in range(sims):
        prices = [capital]
        for _ in range(days):
            change = np.random.normal(mean, std)
            prices.append(prices[-1]*(1+change))
        paths.append(prices)

    fig = go.Figure()
    for p in paths[:20]:
        fig.add_trace(go.Scatter(y=p, showlegend=False))

    st.plotly_chart(fig)

# =========================
# RAW DATA
# =========================
with tab7:
    raw = df[df["fund"].isin(selected)].copy()

    if raw.empty:
        st.warning("Geen data voor selectie")
    else:
        st.dataframe(raw)
