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
# CALCULATIONS
# =========================
ret = (pivot.iloc[-1] / pivot.iloc[0] - 1) * 100 if len(pivot) > 1 else None
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
# OVERVIEW (HERSTELD)
# =========================
with tab1:
    st.subheader("Overview")

    start_date = pivot.index.min().strftime("%d-%m-%Y")
    end_date = pivot.index.max().strftime("%d-%m-%Y")
    days = (pivot.index.max() - pivot.index.min()).days

    st.caption(f"Periode: {start_date} → {end_date} ({days} dagen)")

    if ret is not None:
        best = ret.idxmax()
        worst = ret.idxmin()

        c1,c2,c3,c4,c5 = st.columns(5)

        c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
        c2.metric("Beste fonds", best)
        c3.metric("Slechtste fonds", worst)
        c4.metric("Volatiliteit", f"{vol.mean():.2f}")
        c5.metric("Sharpe", f"{sharpe.mean():.2f}")

        st.subheader("AI Insights")
        st.info(f"""
Beste fonds: {best} (+{ret.max():.2f}%)
Slechtste fonds: {worst} ({ret.min():.2f}%)
Hoogste risico: {vol.idxmax()}
""")

    st.markdown("---")

    # Trend 1
    st.subheader("Prijsontwikkeling")

    fig = go.Figure()
    benchmark = pivot.mean(axis=1)

    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[col], name=col))

    fig.add_trace(go.Scatter(
        x=pivot.index,
        y=benchmark,
        name="Benchmark",
        line=dict(dash="dash")
    ))

    st.plotly_chart(fig, use_container_width=True)

    # Trend 2
    st.subheader("Genormaliseerde groei")

    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col))

    st.plotly_chart(fig2, use_container_width=True)

    # Drawdown
    st.subheader("Drawdown")

    fig3 = go.Figure()
    for col in drawdown.columns:
        fig3.add_trace(go.Scatter(x=drawdown.index, y=drawdown[col]*100, name=col))

    st.plotly_chart(fig3, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    st.subheader("Momentum")

    if len(pivot) < 30:
        st.warning("Minimaal 30 dagen data nodig")
    else:
        mom = (pivot / pivot.shift(30) - 1) * 100
        st.bar_chart(mom.iloc[-1].dropna())

# =========================
# RISK (UITGEBREID)
# =========================
with tab3:
    st.subheader("Risk")

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe,
        "Max Drawdown %": max_dd * 100
    })

    st.dataframe(risk_df, use_container_width=True)

    st.subheader("Rolling Volatility")
    rolling_vol = returns.rolling(30).std() * np.sqrt(TRADING_DAYS)

    fig = go.Figure()
    for col in rolling_vol.columns:
        fig.add_trace(go.Scatter(x=rolling_vol.index, y=rolling_vol[col], name=col))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Correlation")
    fig_corr = px.imshow(returns.corr(), text_auto=True)
    fig_corr.update_layout(height=700)
    st.plotly_chart(fig_corr, use_container_width=True)

# =========================
# HEATMAP (VOLLEDIG HERSTELD)
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {
        "1D":1,"2D":2,"3D":3,"4D":4,
        "1W":7,"2W":14,"3W":21,
        "1M":30,"2M":60,"3M":90,"6M":180,
        "1Y":365,"2Y":730,"5Y":1825
    }

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
        zmid=0,
        text=np.round(heat.values,2),
        texttemplate="%{text}%"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER (ECHT)
# =========================
with tab5:
    st.subheader("Optimizer (Max Sharpe)")

    st.caption(
        "De optimizer zoekt de beste verdeling van fondsen op basis van historische data.\n"
        "Doel: maximaal rendement met zo laag mogelijk risico (Sharpe ratio)."
    )

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

        # =========================
        # UITLEG
        # =========================
        st.markdown("### Wat zie je hier?")
        st.info(
            "Elke punt in de grafiek is een mogelijke portfolio.\n\n"
            "• X-as = risico (volatiliteit)\n"
            "• Y-as = verwacht rendement\n"
            "• Kleur = Sharpe ratio (groen = beter)\n\n"
            "De optimizer kiest de portfolio met de hoogste Sharpe ratio."
        )

        # =========================
        # BESTE VERDELING
        # =========================
        st.subheader("Optimale verdeling")

        opt_df = pd.DataFrame({
            "Fund": mean_returns.index,
            "Weight %": best_weights * 100
        }).sort_values("Weight %", ascending=False)

        st.dataframe(opt_df, use_container_width=True)

        st.caption(
            "Deze verdeling maximaliseert rendement per risico-eenheid.\n"
            "Hogere percentages betekenen grotere allocatie in dat fonds."
        )

        # =========================
        # FRONTIER
        # =========================
        st.subheader("Efficient Frontier")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=results[:,1],
            y=results[:,0],
            mode="markers",
            marker=dict(
                color=results[:,2],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Sharpe")
            ),
            name="Portfolios"
        ))

        fig.update_layout(
            xaxis_title="Risico (volatiliteit)",
            yaxis_title="Rendement",
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)

        # =========================
        # EXTRA UITLEG
        # =========================
        st.markdown("### Hoe lees je dit?")
        st.markdown(
            """
- Linksonder = laag risico, laag rendement  
- Rechtsboven = hoog risico, hoog rendement  
- Beste punt = hoogste Sharpe ratio (beste balans)

💡 Tip:
Een goede portfolio ligt meestal niet extreem rechts (te risicovol), maar ook niet helemaal links (te weinig rendement).
"""
        )
# =========================
# REBALANCE (MONTE CARLO)
# =========================
with tab6:
    st.subheader("Monte Carlo")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    if returns.shape[0] < 30:
        st.warning("Te weinig data voor simulatie")
    else:
        mean = returns.mean().mean()
        std = returns.std().mean()

        sims = 200
        days = 100

        paths = []

        for _ in range(sims):
            prices = [capital]
            for _ in range(days):
                change = np.random.normal(mean, std)
                prices.append(prices[-1]*(1+change))
            paths.append(prices)

        paths = np.array(paths)

        expected = paths.mean(axis=0)
        worst = np.percentile(paths,5,axis=0)
        best = np.percentile(paths,95,axis=0)

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