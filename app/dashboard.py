import streamlit as st
import pandas as pd

# =========================
# CONFIG
# =========================
CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

# =========================
# DATA LADEN
# =========================
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_URL)
    df["date"] = pd.to_datetime(df["date"])
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
# NORMALISATIE (% groei)
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

st.subheader("📊 Actuele waardes")
st.dataframe(latest, use_container_width=True)

# =========================
# PERFORMANCE
# =========================
perf = pct.iloc[-1].sort_values(ascending=False)

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏆 Beste fondsen")
    top = perf.head(10).to_frame(name="performance")
    st.bar_chart(top)

with col2:
    st.subheader("📉 Slechtste fondsen")
    worst = perf.tail(10).to_frame(name="performance")
    st.bar_chart(worst)

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
