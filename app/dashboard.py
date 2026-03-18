# =========================
# FIX IMPORT PATH
# =========================
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# =========================
# CONFIG + DB SETUP
# =========================
from app.config import DB_PATH
from pipeline.database import init_db
from pipeline.runner import run

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db()

# =========================
# LIBRARIES
# =========================
import streamlit as st
import sqlite3
import pandas as pd

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

df = pd.read_csv(CSV_URL)

from app.analytics import normalize, performance, volatility, sharpe_ratio

# =========================
# ZORG DAT DATA BESTAAT
# =========================
conn = sqlite3.connect(DB_PATH)

try:
    count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
except:
    count = 0

conn.close()

if count == 0:
    with st.spinner("Data ophalen..."):
        try:
            run()
        except Exception as e:
            st.error(f"Fout bij ophalen data: {e}")

# =========================
# DASHBOARD UI
# =========================
st.set_page_config(layout="wide")
st.title("📈 Funds Intelligence Dashboard")

# =========================
# DATA LADEN
# =========================
import pandas as pd

CSV_URL = "https://raw.githubusercontent.com/joelpfeiffer/FundData/main/data/prices.csv"

df = pd.read_csv(CSV_URL)

if df.empty:
    st.warning("Geen data beschikbaar")
    st.stop()

# =========================
# DATA PREP
# =========================
df["date"] = pd.to_datetime(df["date"])
pivot = df.pivot(index="date", columns="fund", values="price")

# =========================
# FILTERS
# =========================
selected = st.multiselect(
    "Selecteer fondsen",
    pivot.columns,
    default=list(pivot.columns)[:5]
)

if not selected:
    st.warning("Selecteer minimaal 1 fonds")
    st.stop()

pivot = pivot[selected]

# =========================
# ANALYSE
# =========================
norm = normalize(pivot)
perf = performance(norm)

# =========================
# VISUALS
# =========================
st.subheader("📊 Groei (genormaliseerd)")
st.line_chart(norm)

st.subheader("🏆 Performance (%)")
st.dataframe(perf)

st.subheader("⚡ Volatility")
st.dataframe(volatility(norm))

st.subheader("📉 Sharpe Ratio")
st.dataframe(sharpe_ratio(norm))

# =========================
# BESTE FONDS
# =========================
if not perf.empty:
    best = perf.index[0]
    st.success(f"🏆 Beste fonds: {best}")
