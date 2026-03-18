import streamlit as st
import pandas as pd
import numpy as np
import time

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

# =========================
# REFRESH
# =========================
if st.button("🔄 Refresh data"):
    st.cache_data.clear()

# =========================
# DATA LADEN
# =========================
@st.cache_data(ttl=60)
def load_data():
    url = f"{CSV_URL}?t={int(time.time())}"
    df = pd.read_csv(url)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df

df = load_data()

if df.empty:
    st.warning("Geen data beschikbaar")
    st.stop()

# =========================
# DATA PREP
# =========================
pivot = df.pivot(index="date", columns="fund", values="price")

selected = st.multiselect(
    "Selecteer fondsen",
    pivot.columns,
    default=list(pivot.columns)[:5]
)

pivot = pivot[selected]

# =========================
# GROEI (%)
# =========================
norm = pivot / pivot.iloc[0]
pct = (norm - 1) * 100

# =========================
# GRAFIEK
# =========================
st.subheader("📈 Groei (%)")
st.line_chart(pct)

# =========================
# ACTUELE WAARDES
# =========================
latest = df.sort_values("date").groupby("fund").last().reset_index()
latest = latest[latest["fund"].isin(selected)]

st.subheader("📊 Actuele waardes")
st.dataframe(latest, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
perf = pct.iloc[-1].sort_values(ascending=False)

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Beste fondsen")
    st.bar_chart(perf.head(10).to_frame(name="performance"))

with col2:
    st.subheader("📉 Slechtste fondsen")
    st.bar_chart(perf.tail(10).to_frame(name="performance"))

# =========================
# METRICS
# =========================
best_fund = perf.idxmax()
best_value = perf.max()

worst_fund = perf.idxmin()
worst_value = perf.min()

col1, col2 = st.columns(2)

with col1:
    st.metric("🏆 Beste fonds", best_fund, f"{best_value:.2f}%")

with col2:
    st.metric("📉 Slechtste fonds", worst_fund, f"{worst_value:.2f}%")

# =========================
# OVERZICHT
# =========================
summary = latest.copy().set_index("fund")
summary["groei_%"] = perf

st.subheader("📋 Overzicht")
st.dataframe(
    summary.sort_values("groei_%", ascending=False),
    use_container_width=True
)

# =========================
# 🔥 HEATMAP
# =========================
st.subheader("🔥 Rendement Heatmap")

latest_date = df["date"].max()

def calc_return(days):
    results = {}

    for fund in df["fund"].unique():
        fund_df = df[df["fund"] == fund].sort_values("date")

        current_price = fund_df.iloc[-1]["price"]
        target_date = latest_date - pd.Timedelta(days=days)

        past_df = fund_df[fund_df["date"] <= target_date]

        if past_df.empty:
            results[fund] = np.nan
        else:
            past_price = past_df.iloc[-1]["price"]
            results[fund] = (current_price / past_price - 1) * 100

    return pd.Series(results)

periods = {
    "1D": 1,
    "3D": 3,
    "1W": 7,
    "2W": 14,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "3Y": 365*3,
    "5Y": 365*5
}

heatmap = pd.DataFrame({
    name: calc_return(days)
    for name, days in periods.items()
})

heatmap = heatmap.loc[heatmap.index.intersection(selected)]

# =========================
# 🎨 KLEUREN (JOUW LOGICA)
# =========================
def color_gradient(val, col):
    if pd.isna(val):
        return "background-color: #111; color: #666"

    short_cols = ["1D", "3D", "1W", "2W"]

    # 📉 KORTE TERMIJN (<1M)
    if col in short_cols:
        if val < -0.01:
            return "background-color: #ff0000; color: white"
        elif val < 0:
            return "background-color: #f4a261"
        elif val < 0.25:
            return "background-color: #ffcc00"
        elif val < 0.5:
            return "background-color: #a8d08d"
        elif val < 0.75:
            return "background-color: #70ad47"
        else:
            return "background-color: #548235; color: white"

    # 📈 LANGE TERMIJN (≥1M)
    else:
        if val < -0.01:
            return "background-color: #ff0000; color: white"
        elif val < 2.5:
            return "background-color: #f4a261"
        elif val < 4:
            return "background-color: #ffcc00"
        elif val < 10:
            return "background-color: #a8d08d"
        elif val < 25:
            return "background-color: #70ad47"
        else:
            return "background-color: #548235; color: white"

# =========================
# STYLING
# =========================
styled = heatmap.style.format(
    lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%" if pd.notna(x) else ""
)

for col in heatmap.columns:
    styled = styled.apply(
        lambda s: [color_gradient(v, col) for v in s],
        subset=[col]
    )

styled = styled.set_properties(**{
    "text-align": "center",
    "font-weight": "600",
    "font-size": "13px",
    "font-family": "monospace"
})

st.dataframe(styled, use_container_width=True, height=500)
