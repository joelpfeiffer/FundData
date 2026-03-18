import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"
TRADING_DAYS = 252

st.set_page_config(layout="wide")

# =========================
# ONBOARDING
# =========================
if "onboarding" not in st.session_state:
    st.session_state.onboarding = True

if st.session_state.onboarding:
    st.info("""
Welkom in het dashboard.

• Selecteer fondsen links  
• Kies timeframe  
• Bekijk trends, risico en simulaties  

Gebruik de ℹ️ knoppen voor uitleg.
""")
    if st.button("Start"):
        st.session_state.onboarding = False

# =========================
# DATA
# =========================
@st.cache_data(ttl=60)
def load():
    df = pd.read_csv(f"{CSV_URL}?t={int(time.time())}")
    df["date"] = pd.to_datetime(df["date"])
    return df

df = load()
pivot_full = df.pivot(index="date", columns="fund", values="price")

# =========================
# SIDEBAR
# =========================
funds = list(pivot_full.columns)

selected = st.sidebar.multiselect("Fondsen", funds, default=funds[:5])

# RESET ONBOARDING
st.sidebar.markdown("---")
if st.sidebar.button("Start onboarding opnieuw"):
    st.session_state.onboarding = True

# =========================
# TIMEFRAME
# =========================
mode = st.sidebar.radio("Timeframe", ["Preset", "Custom"])

pivot = pivot_full[selected]

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
# TOOLTIP
# =========================
def tooltip(title, text):
    col1, col2 = st.columns([20,1])
    with col1:
        st.subheader(title)
    with col2:
        if st.button("ℹ️", key=title):
            st.session_state[title] = True

    if st.session_state.get(title, False):
        st.info(text)

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

    tooltip("Trend", """
Hier zie je de prijsontwikkeling van fondsen.

• X-as = tijd  
• Y-as = prijs  
• Gebruik dit om trends te herkennen  
""")

    fig = go.Figure()

    for col in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[col],
            name=col
        ))

    fig.update_layout(
        xaxis_rangeslider_visible=True,  # RULER
        xaxis_title="Datum",
        yaxis_title="Prijs"
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
with tab2:
    tooltip("Momentum", "Performance over recente periode")

    if len(pivot) > 1:
        mom = (pivot / pivot.shift(30) - 1) * 100
        last = mom.iloc[-1].dropna()

        if not last.empty:
            df_plot = last.sort_values(ascending=False)

            fig = go.Figure(go.Bar(
                x=df_plot.index,
                y=df_plot.values
            ))

            st.plotly_chart(fig, use_container_width=True)

# =========================
# RISK
# =========================
with tab3:
    tooltip("Risk analyse", """
Risico analyse van fondsen

• Volatility = schommeling  
• Sharpe = rendement vs risico  
""")

    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean()*TRADING_DAYS)/vol

    st.dataframe(vol.to_frame("Volatility"))
    st.dataframe(sharpe.to_frame("Sharpe"))

# =========================
# HEATMAP (FIXED COLORS)
# =========================
with tab4:
    tooltip("Heatmap", "Groen = positief rendement, rood = negatief")

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
    heatmap = heatmap.loc[selected]

    fig = go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns,
        y=heatmap.index,
        colorscale=[
            [0, "red"],
            [0.5, "white"],
            [1, "green"]
        ],
        zmid=0,
        text=heatmap.round(2).astype(str)+"%",
        texttemplate="%{text}"
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# OPTIMIZER
# =========================
with tab5:
    st.subheader("Optimizer")

# =========================
# REBALANCE + MONTE CARLO
# =========================
with tab6:

    st.subheader("Portfolio")

    capital = st.number_input("Kapitaal", 100, 1000000, 10000)

    weights = np.ones(len(selected)) / len(selected)

    port = (returns[selected] * weights).sum(axis=1)

    st.subheader("Simulatie")

    value = capital * (1 + port).cumprod()
    st.line_chart(value)

    # MONTE CARLO FIX
    st.subheader("Monte Carlo")

    if len(port) > 20:
        sims = np.random.normal(port.mean(), port.std(), (252, 200))
        sims = capital * np.cumprod(1 + sims, axis=0)

        mc = pd.DataFrame({
            "Worst": np.percentile(sims,10,axis=1),
            "Expected": np.percentile(sims,50,axis=1),
            "Best": np.percentile(sims,90,axis=1)
        })

        st.line_chart(mc)