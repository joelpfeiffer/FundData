import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import time

st.set_page_config(layout="wide")

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date","price","fund"])
    return df.sort_values("date")

df = load_data()

if df.empty:
    st.error("Geen data beschikbaar")
    st.stop()

pivot_full = df.pivot(index="date", columns="fund", values="price")

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

st.sidebar.markdown("---")
st.sidebar.button("Start onboarding")

# =========================
# FILTER DATA
# =========================
if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot_full[selected].copy()

if mode == "Preset" and tf != "ALL":
    pivot = pivot[pivot.index >= pivot.index.max() - pd.Timedelta(days=days_map[tf])]
elif mode == "Custom":
    pivot = pivot[(pivot.index >= pd.to_datetime(start)) & (pivot.index <= pd.to_datetime(end))]

pivot = pivot.dropna(how="all")

if pivot.empty:
    st.warning("Geen data in deze periode")
    st.stop()

returns = pivot.pct_change().dropna()

# =========================
# PRE CALC
# =========================
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100 if len(pivot) > 1 else None
vol = returns.std() * np.sqrt(TRADING_DAYS)
sharpe = (returns.mean()*TRADING_DAYS)/vol.replace(0,np.nan)

# =========================
# TABS
# =========================
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "Overview","Performance","Risk","Heatmap","Optimizer","Rebalance","Raw Data"
])

# =========================
# OVERVIEW (ongewijzigd)
# =========================
with tab1:
    st.subheader("Overview")

    if ret is not None:
        best = ret.idxmax()
        worst = ret.idxmin()

        c1,c2,c3,c4,c5 = st.columns(5)

        c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
        c2.metric("Beste fonds", best)
        c3.metric("Slechtste fonds", worst)
        c4.metric("Volatiliteit", f"{vol.mean():.2f}")
        c5.metric("Sharpe", f"{sharpe.mean():.2f}")

    # trend
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE (FIX)
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) < 30:
        st.warning("Minimaal 30 dagen data nodig voor momentum")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        st.bar_chart(mom.iloc[-1].dropna())

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Risk")

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe
    })

    st.dataframe(risk_df)

    fig_corr = px.imshow(returns.corr(), text_auto=True)
    fig_corr.update_layout(height=700)
    st.plotly_chart(fig_corr)

# =========================
# HEATMAP
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {"1W":7,"1M":30,"3M":90,"6M":180,"1Y":365}

    def calc(days):
        past = pivot_full[pivot_full.index <= latest - pd.Timedelta(days=days)]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest] / past.iloc[-1] - 1) * 100

    heat = pd.DataFrame({k:calc(v) for k,v in periods.items()}).loc[selected]

    fig = go.Figure(data=go.Heatmap(
        z=heat.values,
        x=heat.columns,
        y=heat.index,
        colorscale=[
            [0, "#d73027"],
            [0.5, "#f5e6a3"],
            [1, "#1a9850"]
        ],
        zmid=0
    ))

    st.plotly_chart(fig)

# =========================
# OPTIMIZER (ECHT)
# =========================
with tab5:
    st.subheader("Optimizer")

    if returns.shape[1] < 2:
        st.warning("Minimaal 2 fondsen nodig")
    else:
        mean_returns = returns.mean()*TRADING_DAYS
        cov = returns.cov()*TRADING_DAYS

        results = []
        weights_list = []

        for _ in range(5000):
            w = np.random.random(len(mean_returns))
            w /= w.sum()

            r = np.dot(w, mean_returns)
            v = np.sqrt(np.dot(w.T, np.dot(cov, w)))
            s = r / v if v != 0 else 0

            results.append([r,v,s])
            weights_list.append(w)

        results = np.array(results)

        best_idx = np.argmax(results[:,2])
        best_weights = weights_list[best_idx]

        st.dataframe(pd.DataFrame({
            "Fund": mean_returns.index,
            "Weight %": best_weights*100
        }))

        # frontier
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=results[:,1],
            y=results[:,0],
            mode="markers",
            marker=dict(color=results[:,2], colorscale="Viridis")
        ))

        fig.update_layout(xaxis_title="Risk", yaxis_title="Return")
        st.plotly_chart(fig)

# =========================
# REBALANCE (MONTE CARLO TERUG)
# =========================
with tab6:
    st.subheader("Rebalance + Monte Carlo")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    if returns.shape[0] < 30:
        st.warning("Te weinig data voor Monte Carlo")
    else:
        mean = returns.mean().mean()
        std = returns.std().mean()

        days = 100
        sims = 200

        paths = []

        for _ in range(sims):
            prices = [capital]
            for _ in range(days):
                change = np.random.normal(mean, std)
                prices.append(prices[-1]*(1+change))
            paths.append(prices)

        paths = np.array(paths)

        expected = paths.mean(axis=0)
        worst = np.percentile(paths, 5, axis=0)
        best = np.percentile(paths, 95, axis=0)

        fig = go.Figure()

        fig.add_trace(go.Scatter(y=expected, name="Expected"))
        fig.add_trace(go.Scatter(y=best, name="Best Case"))
        fig.add_trace(go.Scatter(y=worst, name="Worst Case"))

        st.plotly_chart(fig)

# =========================
# RAW DATA
# =========================
with tab7:
    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)]

    st.dataframe(raw)

    st.download_button("Download CSV", raw.to_csv().encode(), "data.csv")