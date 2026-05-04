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

# ===== CAGR =====
days = (pivot.index[-1] - pivot.index[0]).days
years = days / 365

if years > 0:
    cagr = ((pivot.iloc[-1] / pivot.iloc[0]) ** (1/years) - 1) * 100
else:
    cagr = pd.Series(index=pivot.columns, dtype=float)

# ===== SORTINO =====
downside = returns.copy()
downside[downside > 0] = 0
downside_std = downside.std() * np.sqrt(TRADING_DAYS)

sortino = (returns.mean()*TRADING_DAYS) / downside_std.replace(0,np.nan)

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

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)

    c1.metric("Gem. rendement", f"{ret.mean():.2f}%")
    c2.metric("Beste fonds", best)
    c3.metric("Slechtste fonds", worst)
    c4.metric("Volatiliteit", f"{vol.mean():.2f}")
    c5.metric("Sharpe", f"{sharpe.mean():.2f}")
    c6.metric("CAGR", f"{cagr.mean():.2f}%")
    c7.metric("Sortino", f"{sortino.mean():.2f}")

    if vol.notna().any():
        risico_txt = f"{vol.idxmax()} (volatiliteit {vol.max():.2f})"
    else:
        risico_txt = "Geen volatiliteitsdata"

    st.info(f"""
Beste: {best} (+{ret.max():.2f}%)
Slechtste: {worst} ({ret.min():.2f}%)
Hoogste risico: {risico_txt}
""")

    # ===== PRIJS =====
    fig = go.Figure()
    for col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index,y=pivot[col],name=col))
    st.plotly_chart(fig,use_container_width=True)

    # ===== GENORMALISEERD =====
    st.subheader("Genormaliseerde groei (index = 100)")
    norm = pivot / pivot.iloc[0] * 100

    fig2 = go.Figure()
    for col in norm.columns:
        fig2.add_trace(go.Scatter(x=norm.index,y=norm[col],name=col))
    st.plotly_chart(fig2, use_container_width=True)

    # ===== DRAWDOWN =====
    st.subheader("Drawdown")
    fig3 = go.Figure()
    for col in drawdown.columns:
        fig3.add_trace(go.Scatter(x=drawdown.index,y=drawdown[col]*100,name=col))
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
        mom_last = mom.iloc[-1].dropna().to_frame(name="Momentum")
        mom_last["Fund"] = mom_last.index
        st.bar_chart(mom_last.set_index("Fund"))

# =========================
# RISK
# =========================
with tab3:
    st.subheader("Risk")

    risk_df = pd.DataFrame({
        "Volatility": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "CAGR %": cagr,
        "Max Drawdown %": max_dd * 100
    })

    st.dataframe(risk_df, use_container_width=True)

    st.subheader("Rolling Volatility")
    if len(returns) >= 30:
        rolling_vol = returns.rolling(30).std() * np.sqrt(TRADING_DAYS)
        fig = go.Figure()
        for col in rolling_vol.columns:
            fig.add_trace(go.Scatter(x=rolling_vol.index,y=rolling_vol[col],name=col))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Correlation")
    corr = returns.corr()
    fig_corr = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale="RdYlGn",
        zmid=0
    ))
    st.plotly_chart(fig_corr, use_container_width=True)

# =========================
# HEATMAP
# =========================
with tab4:
    st.subheader("Heatmap")

    latest = pivot_full.index.max()

    periods = {"1D":1,"1W":7,"1M":30,"3M":90,"6M":180,"1Y":365}

    def calc(days):
        cutoff = latest - pd.Timedelta(days=days)
        past = pivot_full[pivot_full.index <= cutoff]
        if past.empty:
            return pd.Series(index=pivot_full.columns)
        return (pivot_full.loc[latest] / past.iloc[-1] - 1) * 100

    heat = pd.DataFrame({k:calc(v) for k,v in periods.items()})
    heat = heat.reindex(selected).dropna(how="all")

    if not heat.empty:
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
    st.subheader("Optimizer (Portfolio Profielen)")

    if returns.shape[1] < 2:
        st.warning("Minimaal 2 fondsen nodig")
        st.stop()

    # =========================
    # DATA
    # =========================
    mean_returns = returns.mean() * TRADING_DAYS
    cov_matrix = returns.cov() * TRADING_DAYS

    num_assets = len(mean_returns)

    results = []
    weights_list = []

    # =========================
    # MONTE CARLO SIMULATIE
    # =========================
    for _ in range(4000):
        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        port_return = np.dot(weights, mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        if port_vol == 0:
            port_sharpe = 0
        else:
            port_sharpe = port_return / port_vol

        results.append([port_return, port_vol, port_sharpe])
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
    # RESULTAAT TABEL
    # =========================
    st.subheader("Portfolio verdeling")

    df_profile = pd.DataFrame({
        "Fund": mean_returns.index,
        "Weight %": selected_weights * 100
    }).sort_values("Weight %", ascending=False)

    st.dataframe(df_profile, use_container_width=True)

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
    # EFFICIENT FRONTIER
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
            prices.append(prices[-1]*(1+np.random.normal(mean,std)))
        paths.append(prices)

    fig = go.Figure()
    for p in paths[:20]:
        fig.add_trace(go.Scatter(y=p, showlegend=False))
    st.plotly_chart(fig)

# =========================
# RAW DATA
# =========================
with tab7:
    st.subheader("Raw Data")

    raw = df[df["fund"].isin(selected)].copy()

    if not raw.empty:
        view = st.radio("Weergave", ["Long","Wide"], horizontal=True)

        if view == "Long":
            display = raw.sort_values("date")
        else:
            display = raw.pivot_table(index="date",columns="fund",values="price").sort_index()

        st.dataframe(display, use_container_width=True)

        st.download_button(
            "Download CSV",
            display.to_csv().encode(),
            "fund_data.csv",
            mime="text/csv"
        )
