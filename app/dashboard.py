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
# REFRESH BUTTON
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
# 🔥 HEATMAP (PRO)
# =========================
st.subheader("🔥 Rendement Heatmap")

latest_date = df["date"].max()

def calc_return(days):
    past_date = latest_date - pd.Timedelta(days=days)

    past = (
        df[df["date"] <= past_date]
        .sort_values("date")
        .groupby("fund")
        .last()
    )

    current = (
        df.sort_values("date")
        .groupby("fund")
        .last()
    )

    merged = current[["price"]].join(
        past[["price"]],
        lsuffix="_now",
        rsuffix="_past"
    )

    merged["return"] = (merged["price_now"] / merged["price_past"] - 1) * 100

    return merged["return"]

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

def color_gradient(val):
    if pd.isna(val):
        return ""

    val = max(min(val, 10), -10)

    if val > 0:
        intensity = int(255 - (val / 10) * 155)
        return f"background-color: rgb({intensity},255,{intensity})"
    else:
        intensity = int(255 - (abs(val) / 10) * 155)
        return f"background-color: rgb(255,{intensity},{intensity})"

styled = (
    heatmap.style
    .format("{:.2f}%")
    .applymap(color_gradient)
    .set_properties(**{
        "text-align": "center",
        "font-weight": "600"
    })
)

st.dataframe(styled, use_container_width=True, height=500)
