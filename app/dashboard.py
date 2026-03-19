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

        c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("Gem. rendement", f"{ret.mean():.2f}%")

with c2:
    st.metric("Beste fonds", best)
    st.caption(best)

with c3:
    st.metric("Slechtste fonds", worst)
    st.caption(worst)

with c4:
    st.metric("Volatiliteit", f"{vol.mean():.2f}")

with c5:
    st.metric("Sharpe", f"{sharpe.mean():.2f}")

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
    st.subheader("Optimizer (Portfolio Profielen)")

    st.caption(
        "Deze optimizer berekent duizenden mogelijke portfolio’s en selecteert de beste "
        "combinaties op basis van risico en rendement (Sharpe ratio)."
    )

    if returns.shape[1] < 2:
        st.warning("Minimaal 2 fondsen nodig")
        st.stop()

    # =========================
    # DATA
    # =========================
    mean_returns = returns.mean() * TRADING_DAYS
    cov_matrix = returns.cov() * TRADING_DAYS

    results = []
    weights_list = []

    num_assets = len(mean_returns)

    # =========================
    # SIMULATIE
    # =========================
    for _ in range(4000):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        ret = np.dot(weights, mean_returns)
        vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = ret / vol if vol != 0 else 0

        results.append([ret, vol, sharpe])
        weights_list.append(weights)

    results = np.array(results)

    # =========================
    # PROFIELEN
    # =========================
    idx_min_risk = np.argmin(results[:,1])
    idx_max_return = np.argmax(results[:,0])
    idx_max_sharpe = np.argmax(results[:,2])
    idx_balanced = np.argsort(results[:,2])[len(results)//2]

    profiles = {
        "Low Risk": idx_min_risk,
        "Balanced": idx_balanced,
        "High Return": idx_max_return,
        "Max Sharpe": idx_max_sharpe
    }

    selected_profile = st.selectbox(
        "Kies risicoprofiel",
        list(profiles.keys()),
        index=3
    )

    selected_idx = profiles[selected_profile]
    selected_weights = weights_list[selected_idx]

    # =========================
    # UITLEG
    # =========================
    st.markdown("### Wat betekent dit?")
    st.info(
        f"Profiel: **{selected_profile}**\n\n"
        "• Low Risk = minimale schommelingen\n"
        "• Balanced = middenweg\n"
        "• High Return = maximale groei (meer risico)\n"
        "• Max Sharpe = beste balans tussen risico en rendement\n\n"
        "Hover over punten in de grafiek om de exacte fondsverdeling te zien."
    )

    # =========================
    # RESULTAAT TABEL (ENKEL!)
    # =========================
    st.subheader("Portfolio verdeling")

    df_profile = pd.DataFrame({
        "Fund": mean_returns.index,
        "Weight %": selected_weights * 100
    }).sort_values("Weight %", ascending=False)

    st.dataframe(df_profile, use_container_width=True)

    st.caption(
        "Deze verdeling laat zien hoeveel procent van je investering in elk fonds zit "
        "voor het gekozen risicoprofiel."
    )

    # =========================
    # HOVER DATA
    # =========================
    hover_text = []

    for w in weights_list:
        txt = "<br>".join([
            f"{fund}: {weight*100:.1f}%"
            for fund, weight in zip(mean_returns.index, w)
        ])
        hover_text.append(txt)

    # =========================
    # FRONTIER
    # =========================
    st.subheader("Efficient Frontier")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=results[:,1],
        y=results[:,0],
        mode="markers",
        text=hover_text,
        hovertemplate=
            "<b>Portfolio</b><br>" +
            "Return: %{y:.2f}<br>" +
            "Risk: %{x:.2f}<br><br>" +
            "%{text}<extra></extra>",
        marker=dict(
            color=results[:,2],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Sharpe"),
            size=6
        ),
        name="Portfolios"
    ))

    # =========================
    # HIGHLIGHT SELECTIE
    # =========================
    fig.add_trace(go.Scatter(
        x=[results[selected_idx,1]],
        y=[results[selected_idx,0]],
        mode="markers",
        marker=dict(size=14, color="red"),
        name=selected_profile
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
- Links = laag risico  
- Rechts = hoog risico  
- Boven = hoger rendement  

💡 Het rode punt is jouw gekozen portfolio.

👉 Gebruik de hover om precies te zien hoe de fondsen verdeeld zijn.
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

    raw = df[df["fund"].isin(selected)].copy()

    if raw.empty:
        st.warning("Geen data voor selectie")
        st.stop()

    # =========================
    # VIEW SELECTOR
    # =========================
    view = st.radio(
        "Weergave",
        ["Long", "Wide"],
        horizontal=True
    )

    # =========================
    # LONG FORMAT
    # =========================
    if view == "Long":
        display = raw.sort_values("date")

    # =========================
    # WIDE FORMAT (HERSTELD)
    # =========================
    else:
        display = raw.pivot_table(
            index="date",
            columns="fund",
            values="price",
            aggfunc="last"
        ).sort_index()

    # =========================
    # TABEL
    # =========================
    st.dataframe(display, use_container_width=True)

    # =========================
    # DOWNLOAD
    # =========================
    csv = display.to_csv().encode()

    st.download_button(
        "Download CSV",
        csv,
        "fund_data.csv",
        mime="text/csv"
    )